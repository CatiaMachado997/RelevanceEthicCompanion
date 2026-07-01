"""Sprint D Task 5: GET /api/goals/{id} inlines rollup data."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_user_id, get_current_read_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"
GOAL_ID = "22222222-2222-2222-2222-222222222222"


def _db_mock(fetchone_value):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_value
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


def make_app(rollups_mock):
    from routes.goals import router, get_work_rollups_service

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_work_rollups_service] = lambda: rollups_mock
    return app


def test_goal_detail_includes_rollup():
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    goal_row = {
        "id": GOAL_ID,
        "user_id": TEST_USER_ID,
        "title": "Ship V2",
        "description": "desc",
        "status": "active",
        "priority": 1,
        "target_date": None,
        "created_at": now,
        "completed_at": None,
        "metadata": {},
    }
    rollups = MagicMock()
    rollups.get_goal_rollup.return_value = {
        "goal_id": GOAL_ID,
        "user_id": TEST_USER_ID,
        "milestones_total": 5,
        "milestones_hit": 2,
        "tasks_total": 12,
        "tasks_done": 6,
        "progress_pct": 50,
    }
    conn = _db_mock(goal_row)
    app = make_app(rollups)

    with patch("routes.goals.get_db", return_value=conn):
        with TestClient(app) as client:
            resp = client.get(f"/api/goals/{GOAL_ID}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["rollup"] == {
        "milestones_total": 5,
        "milestones_hit": 2,
        "tasks_total": 12,
        "tasks_done": 6,
        "progress_pct": 50,
    }
    rollups.get_goal_rollup.assert_called_once_with(GOAL_ID)


def test_goal_detail_rollup_zero_when_service_returns_empty():
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    goal_row = {
        "id": GOAL_ID,
        "user_id": TEST_USER_ID,
        "title": "Empty",
        "description": None,
        "status": "active",
        "priority": 5,
        "target_date": None,
        "created_at": now,
        "completed_at": None,
        "metadata": {},
    }
    rollups = MagicMock()
    rollups.get_goal_rollup.return_value = {}
    conn = _db_mock(goal_row)
    app = make_app(rollups)

    with patch("routes.goals.get_db", return_value=conn):
        with TestClient(app) as client:
            resp = client.get(f"/api/goals/{GOAL_ID}")

    assert resp.status_code == 200
    assert resp.json()["data"]["rollup"] == {
        "milestones_total": 0,
        "milestones_hit": 0,
        "tasks_total": 0,
        "tasks_done": 0,
        "progress_pct": 0,
    }
