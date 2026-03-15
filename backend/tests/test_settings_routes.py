"""Settings Route Integration Tests — TDD first."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, UTC
import pytest

from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from esl.models import ESLDecision, ESLDecisionStatus

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"

DEFAULTS = {
    "email_notifications": False,
    "push_notifications": False,
    "esl_alerts": True,
    "share_analytics": False,
    "pii_protection": True,
}

SAMPLE_SETTINGS_ROW = {
    **DEFAULTS,
    "user_id": TEST_USER_ID,
    "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
}


def make_db_mock(fetchone_result=None):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


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
    from routes.settings import router as settings_router, get_esl
    app = FastAPI()
    app.include_router(settings_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_esl] = make_mock_esl
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


def test_get_settings_returns_defaults(client):
    """GET /api/settings/ with no DB row → returns defaults."""
    mock_conn, _ = make_db_mock(fetchone_result=None)

    with patch("routes.settings.get_db", return_value=mock_conn):
        response = client.get("/api/settings/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["esl_alerts"] is True
    assert data["data"]["email_notifications"] is False
    assert data["data"]["pii_protection"] is True


def test_get_settings_returns_saved(client):
    """GET /api/settings/ with existing DB row → returns saved values."""
    row = {**SAMPLE_SETTINGS_ROW, "email_notifications": True}
    mock_conn, _ = make_db_mock(fetchone_result=row)

    with patch("routes.settings.get_db", return_value=mock_conn):
        response = client.get("/api/settings/")

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["email_notifications"] is True


def test_update_settings_success(client):
    """PUT /api/settings/ → 200 with saved data."""
    row = {**SAMPLE_SETTINGS_ROW, "push_notifications": True}
    mock_conn, _ = make_db_mock(fetchone_result=row)

    with patch("routes.settings.get_db", return_value=mock_conn):
        response = client.put(
            "/api/settings/",
            json={**DEFAULTS, "push_notifications": True},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["push_notifications"] is True


def test_update_settings_vetoed_by_esl():
    """PUT /api/settings/ when ESL vetoes → 403."""
    mock_esl = MagicMock()
    mock_esl.evaluate_action = AsyncMock(
        return_value=ESLDecision(
            status=ESLDecisionStatus.VETOED,
            reason="Blocked by focus mode",
            confidence=1.0,
        )
    )

    from routes.settings import get_esl
    app = make_app()
    app.dependency_overrides[get_esl] = lambda: mock_esl

    response = TestClient(app).put("/api/settings/", json=DEFAULTS)

    assert response.status_code == 403
    assert "ESL" in response.json()["detail"]
