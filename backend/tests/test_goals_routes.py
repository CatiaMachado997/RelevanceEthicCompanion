"""
Goals Route Integration Tests

TDD-first: tests written before verifying all pass.
Mocks: DB (get_db context manager), ESL (evaluate_action), Auth dependencies.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, UTC
import pytest

from routes.goals import router as goals_router, get_esl
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from esl.models import ESLDecision, ESLDecisionStatus

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_mock_esl():
    mock_esl = MagicMock()
    mock_esl.evaluate_action = AsyncMock(
        return_value=ESLDecision(
            status=ESLDecisionStatus.APPROVED,
            reason="Approved for testing",
            confidence=1.0,
        )
    )
    return mock_esl


def make_app():
    app = FastAPI()
    app.include_router(goals_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_esl] = make_mock_esl
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


def make_db_mock(fetchone_result=None, fetchall_result=None):
    """Build a mock for get_db() context manager."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result
    mock_cursor.fetchall.return_value = fetchall_result or []

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


SAMPLE_GOAL_ROW = {
    "id": "goal-001",
    "user_id": TEST_USER_ID,
    "title": "Launch MVP",
    "description": "Ship the first version",
    "status": "active",
    "priority": 1,
    "target_date": None,
    "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    "completed_at": None,
    "metadata": {},
}


def test_create_goal_success(client):
    """POST /api/goals/ → 201."""
    mock_conn, _ = make_db_mock(fetchone_result=SAMPLE_GOAL_ROW)

    with patch("routes.goals.get_db", return_value=mock_conn):
        response = client.post(
            "/api/goals/",
            json={"title": "Launch MVP", "priority": 1},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["title"] == "Launch MVP"


def test_list_goals_active_only(client):
    """GET /api/goals/ → active goals."""
    mock_conn, _ = make_db_mock(fetchall_result=[SAMPLE_GOAL_ROW])

    with patch("routes.goals.get_db", return_value=mock_conn):
        response = client.get("/api/goals/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["count"] == 1
    assert data["data"][0]["status"] == "active"


def test_update_goal_status(client):
    """PUT /api/goals/{id} with status=completed → updated."""
    completed_row = {
        **SAMPLE_GOAL_ROW,
        "status": "completed",
        "completed_at": datetime(2026, 3, 12, tzinfo=UTC),
    }
    mock_conn, _ = make_db_mock(fetchone_result=completed_row)

    with patch("routes.goals.get_db", return_value=mock_conn):
        response = client.put(
            "/api/goals/goal-001",
            json={"status": "completed"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["status"] == "completed"


def test_complete_goal(client):
    """POST /api/goals/{id}/complete → completed_at set."""
    completed_row = {
        **SAMPLE_GOAL_ROW,
        "status": "completed",
        "completed_at": datetime(2026, 3, 12, tzinfo=UTC),
    }
    mock_conn, _ = make_db_mock(fetchone_result=completed_row)

    with patch("routes.goals.get_db", return_value=mock_conn):
        response = client.post("/api/goals/goal-001/complete")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["status"] == "completed"
    assert data["data"]["completed_at"] is not None


def test_delete_goal_archives(client):
    """DELETE /api/goals/{id} → status=archived."""
    archived_row = {**SAMPLE_GOAL_ROW, "status": "archived"}
    mock_conn, _ = make_db_mock(fetchone_result=archived_row)

    with patch("routes.goals.get_db", return_value=mock_conn):
        response = client.delete("/api/goals/goal-001")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["status"] == "archived"


def test_reorder_goals_success(client):
    """PATCH /api/goals/reorder → 200."""
    mock_conn, _ = make_db_mock()

    with patch("routes.goals.get_db", return_value=mock_conn):
        response = client.patch(
            "/api/goals/reorder",
            json={"goalIds": ["goal-001", "goal-002"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_complete_goal_calls_esl(client):
    """POST /api/goals/{id}/complete → ESL evaluate_action must be called."""
    completed_row = {
        **SAMPLE_GOAL_ROW,
        "status": "completed",
        "completed_at": datetime(2026, 3, 12, tzinfo=UTC),
    }
    mock_conn, _ = make_db_mock(fetchone_result=completed_row)
    mock_esl = make_mock_esl()

    app = make_app()
    app.dependency_overrides[get_esl] = lambda: mock_esl

    with patch("routes.goals.get_db", return_value=mock_conn):
        response = TestClient(app).post("/api/goals/goal-001/complete")

    assert response.status_code == 200
    mock_esl.evaluate_action.assert_awaited_once()


def test_complete_goal_vetoed_by_esl():
    """POST /api/goals/{id}/complete → 403 when ESL vetoes."""
    mock_esl = MagicMock()
    mock_esl.evaluate_action = AsyncMock(
        return_value=ESLDecision(
            status=ESLDecisionStatus.VETOED,
            reason="Blocked by focus mode",
            confidence=1.0,
        )
    )

    app = make_app()
    app.dependency_overrides[get_esl] = lambda: mock_esl

    response = TestClient(app).post("/api/goals/goal-001/complete")

    assert response.status_code == 403
    assert "ESL" in response.json()["detail"]
