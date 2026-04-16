"""Profile Route Integration Tests — TDD first."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from utils.supabase_auth import get_current_user_id, get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_db_mock(fetchone_result=None, fetchall_result=None):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result
    mock_cursor.fetchall.return_value = fetchall_result or []
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


def make_mock_esl():
    from esl.models import ESLDecision, ESLDecisionStatus

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
    from routes.profile import router as profile_router, get_esl

    app = FastAPI()
    app.include_router(profile_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_esl] = make_mock_esl
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


SAMPLE_USER_ROW = {
    "id": TEST_USER_ID,
    "email": "test@example.com",
    "display_name": "Test User",
    "timezone": "UTC",
}


def test_get_profile_returns_user_data(client):
    """GET /api/profile/ → user data + stats."""
    mock_conn, mock_cursor = make_db_mock(fetchone_result=SAMPLE_USER_ROW)
    mock_cursor.fetchall.return_value = []

    with patch("routes.profile.get_db", return_value=mock_conn):
        response = client.get("/api/profile/")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["email"] == "test@example.com"
    assert data["display_name"] == "Test User"
    assert "stats" in data


def test_get_profile_user_not_found(client):
    """GET /api/profile/ when user doesn't exist → 404."""
    mock_conn, _ = make_db_mock(fetchone_result=None)
    with patch("routes.profile.get_db", return_value=mock_conn):
        response = client.get("/api/profile/")
    assert response.status_code == 404


def test_update_profile_saves_name_and_timezone(client):
    """PUT /api/profile/ → 200 with updated data."""
    updated_row = {
        **SAMPLE_USER_ROW,
        "display_name": "New Name",
        "timezone": "America/New_York",
    }
    mock_conn, _ = make_db_mock(fetchone_result=updated_row)

    with patch("routes.profile.get_db", return_value=mock_conn):
        response = client.put(
            "/api/profile/",
            json={"display_name": "New Name", "timezone": "America/New_York"},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["display_name"] == "New Name"
    assert data["timezone"] == "America/New_York"


def test_update_profile_requires_at_least_one_field(client):
    """PUT /api/profile/ with empty body → 400."""
    mock_conn, _ = make_db_mock()
    with patch("routes.profile.get_db", return_value=mock_conn):
        response = client.put("/api/profile/", json={})
    assert response.status_code == 400
