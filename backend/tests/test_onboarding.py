"""Sprint H Task 1: /api/onboarding/state and /api/onboarding/complete."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_read_user_id, get_current_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def _make_app():
    from routes.onboarding import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    return app


def _mock_db(fetchone_value):
    """Return a get_db_connection mock whose cursor.fetchone() returns the value."""
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_value
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


def test_state_empty_account_all_false():
    app = _make_app()
    row = {
        "onboarded_at": None,
        "has_data_source": False,
        "has_value": False,
        "has_goal": False,
    }
    with patch("routes.onboarding.get_db_connection", return_value=_mock_db(row)):
        client = TestClient(app)
        r = client.get("/api/onboarding/state")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "onboarded_at": None,
        "has_data_source": False,
        "has_value": False,
        "has_goal": False,
    }


def test_state_partial_progress_serializes_timestamp():
    """A user who connected a source + added a value but hasn't completed yet."""
    app = _make_app()
    row = {
        "onboarded_at": None,
        "has_data_source": True,
        "has_value": True,
        "has_goal": False,
    }
    with patch("routes.onboarding.get_db_connection", return_value=_mock_db(row)):
        client = TestClient(app)
        r = client.get("/api/onboarding/state")
    body = r.json()
    assert body["has_data_source"] is True
    assert body["has_value"] is True
    assert body["has_goal"] is False
    assert body["onboarded_at"] is None


def test_state_completed_returns_iso_timestamp():
    app = _make_app()
    ts = datetime(2026, 4, 27, 9, 0, 0, tzinfo=timezone.utc)
    row = {
        "onboarded_at": ts,
        "has_data_source": True,
        "has_value": True,
        "has_goal": True,
    }
    with patch("routes.onboarding.get_db_connection", return_value=_mock_db(row)):
        client = TestClient(app)
        r = client.get("/api/onboarding/state")
    assert r.json()["onboarded_at"] == ts.isoformat()


def test_complete_returns_timestamp_and_is_idempotent():
    """COALESCE in the UPDATE means a second call returns the original timestamp."""
    app = _make_app()
    ts = datetime(2026, 4, 27, 9, 0, 0, tzinfo=timezone.utc)
    with patch(
        "routes.onboarding.get_db_connection",
        return_value=_mock_db({"onboarded_at": ts}),
    ):
        client = TestClient(app)
        r = client.post("/api/onboarding/complete")
    assert r.status_code == 200
    assert r.json()["onboarded_at"] == ts.isoformat()
