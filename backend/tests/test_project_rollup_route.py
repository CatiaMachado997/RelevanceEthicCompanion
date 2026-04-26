"""Sprint D Task 5: GET /api/projects/{id} inlines rollup data."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_user_id, get_current_read_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"
PROJECT_ID = "11111111-1111-1111-1111-111111111111"


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
    from routes.projects import router, get_work_rollups_service

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_work_rollups_service] = lambda: rollups_mock
    return app


def test_project_detail_includes_rollup():
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    project_row = {
        "id": PROJECT_ID,
        "user_id": TEST_USER_ID,
        "title": "Sprint D",
        "description": "desc",
        "status": "active",
        "goal_id": None,
        "created_at": now,
        "updated_at": now,
    }
    rollups = MagicMock()
    rollups.get_project_rollup.return_value = {
        "project_id": PROJECT_ID,
        "user_id": TEST_USER_ID,
        "tasks_total": 10,
        "tasks_done": 4,
        "tasks_open": 6,
        "at_risk_count": 2,
        "completion_pct": 40,
    }
    conn = _db_mock(project_row)
    app = make_app(rollups)

    with patch("routes.projects.get_db_connection", return_value=conn):
        with TestClient(app) as client:
            resp = client.get(f"/api/projects/{PROJECT_ID}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == PROJECT_ID
    assert body["rollup"] == {
        "tasks_total": 10,
        "tasks_done": 4,
        "tasks_open": 6,
        "at_risk_count": 2,
        "completion_pct": 40,
    }
    rollups.get_project_rollup.assert_called_once_with(PROJECT_ID)


def test_project_detail_rollup_zero_when_service_returns_empty():
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    project_row = {
        "id": PROJECT_ID,
        "user_id": TEST_USER_ID,
        "title": "Empty",
        "description": None,
        "status": "active",
        "goal_id": None,
        "created_at": now,
        "updated_at": now,
    }
    rollups = MagicMock()
    rollups.get_project_rollup.return_value = {}
    conn = _db_mock(project_row)
    app = make_app(rollups)

    with patch("routes.projects.get_db_connection", return_value=conn):
        with TestClient(app) as client:
            resp = client.get(f"/api/projects/{PROJECT_ID}")

    assert resp.status_code == 200
    assert resp.json()["rollup"] == {
        "tasks_total": 0,
        "tasks_done": 0,
        "tasks_open": 0,
        "at_risk_count": 0,
        "completion_pct": 0,
    }
