from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from routes.dashboard import router as dashboard_router
from utils.supabase_auth import get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def _client():
    app = FastAPI()
    app.include_router(dashboard_router)
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return TestClient(app)


def _db(fetchone_seq):
    cur = MagicMock()
    cur.fetchone.side_effect = fetchone_seq
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


def test_overview_returns_all_counts():
    client = _client()
    # One fetchone per COUNT query, in the order: goals, tasks, projects, values, documents, transparency, notifications.
    counts = [
        {"cnt": 3},
        {"cnt": 8},
        {"cnt": 2},
        {"cnt": 5},
        {"cnt": 12},
        {"cnt": 42},
        {"cnt": 1},
    ]
    with patch("routes.dashboard.get_db_connection", return_value=_db(counts)):
        r = client.get("/api/dashboard/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["goals_active"] == 3
    assert body["tasks_open"] == 8
    assert body["projects_active"] == 2
    assert body["values_count"] == 5
    assert body["documents_count"] == 12
    assert body["esl_decisions_7d"] == 42
    assert body["notifications_unread"] == 1
