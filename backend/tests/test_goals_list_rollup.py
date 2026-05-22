"""Sprint E Task 4: GET /api/goals/ inlines rollup per goal.

Mirrors test_goal_rollup_route.py — mocks the DB cursor so list rows include
rollup columns from v_goal_rollup; asserts the response shapes them under
`rollup` matching the detail endpoint.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_user_id, get_current_read_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"
GOAL_ID_A = "11111111-1111-1111-1111-111111111111"
GOAL_ID_B = "22222222-2222-2222-2222-222222222222"


def _db_mock(fetchall_value):
    cursor = MagicMock()
    cursor.fetchall.return_value = fetchall_value
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


def make_app():
    from routes.goals import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return app


def test_list_goals_includes_rollup_per_goal():
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    rows = [
        {
            "id": GOAL_ID_A,
            "user_id": TEST_USER_ID,
            "title": "Ship V2",
            "description": "desc",
            "status": "active",
            "priority": 1,
            "target_date": None,
            "created_at": now,
            "completed_at": None,
            "metadata": {},
            "milestones_total": 5,
            "milestones_hit": 2,
            "tasks_total": 12,
            "tasks_done": 6,
            "progress_pct": 50,
        },
        {
            "id": GOAL_ID_B,
            "user_id": TEST_USER_ID,
            "title": "Polish UI",
            "description": None,
            "status": "active",
            "priority": 2,
            "target_date": None,
            "created_at": now,
            "completed_at": None,
            "metadata": {},
            "milestones_total": 0,
            "milestones_hit": 0,
            "tasks_total": 0,
            "tasks_done": 0,
            "progress_pct": 0,
        },
    ]
    conn = _db_mock(rows)
    app = make_app()

    with patch("routes.goals.get_db", return_value=conn):
        with TestClient(app) as client:
            resp = client.get("/api/goals/")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert body["count"] == 2

    g0 = body["data"][0]
    assert g0["id"] == GOAL_ID_A
    assert g0["rollup"] == {
        "milestones_total": 5,
        "milestones_hit": 2,
        "tasks_total": 12,
        "tasks_done": 6,
        "progress_pct": 50,
    }
    # Rollup columns must not leak through as top-level fields.
    for k in (
        "milestones_total",
        "milestones_hit",
        "tasks_total",
        "tasks_done",
        "progress_pct",
    ):
        assert k not in g0, f"rollup key {k} leaked into top-level goal data"

    g1 = body["data"][1]
    assert g1["rollup"] == {
        "milestones_total": 0,
        "milestones_hit": 0,
        "tasks_total": 0,
        "tasks_done": 0,
        "progress_pct": 0,
    }


def test_list_goals_empty():
    conn = _db_mock([])
    app = make_app()

    with patch("routes.goals.get_db", return_value=conn):
        with TestClient(app) as client:
            resp = client.get("/api/goals/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["data"] == []
