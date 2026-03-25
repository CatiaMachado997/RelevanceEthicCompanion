"""Notifications Route Integration Tests — TDD first."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, UTC
import pytest

from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from esl.models import ESLDecision, ESLDecisionStatus

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
    from routes.notifications import router as notif_router, get_esl
    app = FastAPI()
    app.include_router(notif_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_esl] = make_mock_esl
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


SAMPLE_NOTIF = {
    "id": "notif-001",
    "user_id": TEST_USER_ID,
    "type": "goal_completed",
    "title": "Goal Completed",
    "message": "You completed Launch MVP",
    "read": False,
    "created_at": datetime(2026, 3, 15, tzinfo=UTC),
    "metadata": {},
}


def test_list_notifications_returns_data(client):
    """GET /api/notifications/ → list of notifications."""
    mock_conn, _ = make_db_mock(fetchall_result=[SAMPLE_NOTIF])
    with patch("routes.notifications.get_db", return_value=mock_conn):
        response = client.get("/api/notifications/")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["notifications"][0]["type"] == "goal_completed"


def test_list_notifications_unread_filter(client):
    """GET /api/notifications/?unread_only=true → AND read = FALSE in query."""
    mock_conn, mock_cursor = make_db_mock(fetchall_result=[SAMPLE_NOTIF])
    with patch("routes.notifications.get_db", return_value=mock_conn):
        response = client.get("/api/notifications/?unread_only=true")
    assert response.status_code == 200
    # Verify the SQL filter clause was included
    all_sql = " ".join(str(call) for call in mock_cursor.execute.call_args_list)
    assert "read = FALSE" in all_sql


def test_mark_one_read(client):
    """PATCH /api/notifications/{id}/read → marks read."""
    mock_conn, _ = make_db_mock(fetchone_result={**SAMPLE_NOTIF, "read": True})
    with patch("routes.notifications.get_db", return_value=mock_conn):
        response = client.patch("/api/notifications/notif-001/read")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_mark_all_read(client):
    """PATCH /api/notifications/read-all → 200."""
    mock_conn, _ = make_db_mock()
    with patch("routes.notifications.get_db", return_value=mock_conn):
        response = client.patch("/api/notifications/read-all")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_notification_count_endpoint(client, monkeypatch):
    """GET /api/notifications/count returns {unread_count: N}."""
    from unittest.mock import patch, MagicMock
    mock_row = {"cnt": 3}
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = mock_row
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    with patch("routes.notifications.get_db", return_value=mock_conn):
        response = client.get("/api/notifications/count")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 3


def test_esl_veto_creates_notification(client, monkeypatch):
    """create_notification helper writes to user_notifications with correct shape."""
    from routes.notifications import create_notification
    from unittest.mock import MagicMock

    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    create_notification(
        mock_conn,
        user_id="00000000-0000-0000-0000-000000000000",
        type="esl_block",
        title="ESL blocked a response",
        message="Time-based boundary: no work notifications after 7pm",
    )

    mock_cur.execute.assert_called_once()
    args = mock_cur.execute.call_args[0]
    assert "INSERT INTO user_notifications" in args[0]
    assert "esl_block" in args[1]
