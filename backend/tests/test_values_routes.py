"""
Values Route Integration Tests

TDD-first: tests written before verifying all pass.
Mocks: DB (get_db context manager), ESL (evaluate_action), Auth dependencies.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, UTC
import pytest

from routes.values import router as values_router, get_esl
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
    app.include_router(values_router)
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


SAMPLE_VALUE_ROW = {
    "id": "val-001",
    "user_id": TEST_USER_ID,
    "type": "boundary",
    "value": "no_work_after_19h",
    "priority": 1,
    "active": True,
    "metadata": {},
    "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
}


def test_create_value_success(client):
    """POST /api/values/ → 201 with created value."""
    mock_conn, mock_cursor = make_db_mock(fetchone_result=SAMPLE_VALUE_ROW)

    with patch("routes.values.get_db", return_value=mock_conn):
        response = client.post(
            "/api/values/",
            json={"type": "boundary", "value": "no_work_after_19h", "priority": 1},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["value"] == "no_work_after_19h"


def test_create_value_invalid_type(client):
    """POST with bad type → 422 Unprocessable Entity."""
    response = client.post(
        "/api/values/",
        json={"type": "INVALID_TYPE", "value": "some_value", "priority": 1},
    )
    assert response.status_code == 422


def test_list_values_returns_data(client):
    """GET /api/values/ → list of values."""
    mock_conn, _ = make_db_mock(fetchall_result=[SAMPLE_VALUE_ROW])

    with patch("routes.values.get_db", return_value=mock_conn):
        response = client.get("/api/values/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["count"] == 1
    assert len(data["data"]) == 1


def test_update_value_success(client):
    """PUT /api/values/{id} → updated value."""
    updated_row = {**SAMPLE_VALUE_ROW, "value": "no_work_after_18h"}
    mock_conn, _ = make_db_mock(fetchone_result=updated_row)

    with patch("routes.values.get_db", return_value=mock_conn):
        response = client.put(
            "/api/values/val-001",
            json={"value": "no_work_after_18h"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["value"] == "no_work_after_18h"


def test_delete_value_soft_delete(client):
    """DELETE /api/values/{id} → sets active=False."""
    deleted_row = {**SAMPLE_VALUE_ROW, "active": False}
    mock_conn, _ = make_db_mock(fetchone_result=deleted_row)

    with patch("routes.values.get_db", return_value=mock_conn):
        response = client.delete("/api/values/val-001")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["active"] is False


def test_reorder_values_success(client):
    """PATCH /api/values/reorder → 200."""
    mock_conn, _ = make_db_mock()

    with patch("routes.values.get_db", return_value=mock_conn):
        response = client.patch(
            "/api/values/reorder",
            json={"valueIds": ["val-001", "val-002"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_reorder_values_empty_list(client):
    """PATCH with empty valueIds → 400."""
    response = client.patch(
        "/api/values/reorder",
        json={"valueIds": []},
    )
    assert response.status_code == 400
