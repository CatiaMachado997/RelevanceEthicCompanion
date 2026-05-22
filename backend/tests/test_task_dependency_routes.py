"""Sprint D Task 4: tests for goal_id support and dependency sub-routes
on `/api/tasks`."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_user_id, get_current_read_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"
TASK_A = "11111111-1111-1111-1111-111111111111"
TASK_B = "22222222-2222-2222-2222-222222222222"


def make_app(service_mock=None):
    from routes.tasks import router, get_task_dependencies_service, get_esl

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID

    # Bypass ESL for create test
    esl_mock = MagicMock()
    decision = MagicMock()
    decision.status = "APPROVED"
    esl_mock.evaluate_action = AsyncMock(return_value=decision)
    app.dependency_overrides[get_esl] = lambda: esl_mock

    if service_mock is not None:
        app.dependency_overrides[get_task_dependencies_service] = lambda: service_mock
    return app


def _db_mock(per_call_fetchone):
    """Build a get_db_connection mock returning the supplied fetchone values."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = list(per_call_fetchone)

    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def test_create_task_with_goal_id():
    """POST /api/tasks/ with goal_id includes it in INSERT and response."""
    goal_id = "33333333-3333-3333-3333-333333333333"
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    inserted_row = {
        "id": TASK_A,
        "user_id": TEST_USER_ID,
        "project_id": None,
        "goal_id": goal_id,
        "title": "Write tests",
        "description": None,
        "status": "pending",
        "priority": 5,
        "due_date": None,
        "source_origin": "manual",
        "ai_confidence": None,
        "user_confirmed": True,
        "created_at": now,
        "updated_at": now,
    }
    # ESL evaluate may run a context-manager DB query; the create path then
    # runs the INSERT. Provide enough fetchone values; extras are unused.
    conn, cursor = _db_mock([inserted_row, inserted_row, inserted_row])

    app = make_app()
    with patch("routes.tasks.get_db_connection", return_value=conn):
        with TestClient(app) as client:
            resp = client.post(
                "/api/tasks/",
                json={"title": "Write tests", "goal_id": goal_id},
            )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["goal_id"] == goal_id
    assert body["title"] == "Write tests"

    # Find the INSERT call and confirm goal_id was bound.
    insert_calls = [
        c
        for c in cursor.execute.call_args_list
        if "INSERT INTO tasks" in str(c.args[0])
    ]
    assert insert_calls, "expected an INSERT INTO tasks execute call"
    sql, params = insert_calls[0].args
    assert "goal_id" in sql
    assert goal_id in params


def test_get_dependencies_returns_blockers_and_blocked_by():
    blockers = [{"task_id": TASK_B, "title": "B", "status": "pending", "depth": 1}]
    blocked_by = [{"task_id": "x", "title": "X", "status": "done", "depth": 1}]

    service = MagicMock()
    service.get_blockers.return_value = blockers
    service.get_blocked_by.return_value = blocked_by

    # Ownership check fetchone -> truthy
    conn, _cur = _db_mock([(1,)])
    app = make_app(service_mock=service)

    with patch("routes.tasks.get_db_connection", return_value=conn):
        with TestClient(app) as client:
            resp = client.get(f"/api/tasks/{TASK_A}/dependencies")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"blockers": blockers, "blocked_by": blocked_by}
    service.get_blockers.assert_called_once_with(TASK_A)
    service.get_blocked_by.assert_called_once_with(TASK_A)


def test_post_dependency_rejects_cycle():
    service = MagicMock()
    service.add_dependency.side_effect = ValueError(
        "Adding dependency would create a cycle"
    )

    # Two ownership checks (task_id, depends_on_task_id) -> both truthy
    conn, _cur = _db_mock([(1,), (1,)])
    app = make_app(service_mock=service)

    with patch("routes.tasks.get_db_connection", return_value=conn):
        with TestClient(app) as client:
            resp = client.post(
                f"/api/tasks/{TASK_A}/dependencies",
                json={"depends_on_task_id": TASK_B},
            )

    assert resp.status_code == 400
    assert "cycle" in resp.json()["detail"]
    service.add_dependency.assert_called_once_with(TASK_A, TASK_B)


def test_post_dependency_success_returns_ok():
    service = MagicMock()
    service.add_dependency.return_value = None

    conn, _cur = _db_mock([(1,), (1,)])
    app = make_app(service_mock=service)

    with patch("routes.tasks.get_db_connection", return_value=conn):
        with TestClient(app) as client:
            resp = client.post(
                f"/api/tasks/{TASK_A}/dependencies",
                json={"depends_on_task_id": TASK_B},
            )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_delete_dependency_returns_removed_flag():
    service = MagicMock()
    service.remove_dependency.return_value = True

    conn, _cur = _db_mock([(1,)])
    app = make_app(service_mock=service)

    with patch("routes.tasks.get_db_connection", return_value=conn):
        with TestClient(app) as client:
            resp = client.delete(f"/api/tasks/{TASK_A}/dependencies/{TASK_B}")

    assert resp.status_code == 200
    assert resp.json() == {"removed": True}
    service.remove_dependency.assert_called_once_with(TASK_A, TASK_B)

    # And False case
    service.remove_dependency.reset_mock()
    service.remove_dependency.return_value = False
    conn2, _ = _db_mock([(1,)])
    with patch("routes.tasks.get_db_connection", return_value=conn2):
        with TestClient(app) as client:
            resp = client.delete(f"/api/tasks/{TASK_A}/dependencies/{TASK_B}")
    assert resp.status_code == 200
    assert resp.json() == {"removed": False}


def test_dependencies_route_404_for_non_owned_task():
    service = MagicMock()
    conn, _cur = _db_mock([None])  # ownership check fails
    app = make_app(service_mock=service)

    with patch("routes.tasks.get_db_connection", return_value=conn):
        with TestClient(app) as client:
            resp = client.get(f"/api/tasks/{TASK_A}/dependencies")

    assert resp.status_code == 404
    service.get_blockers.assert_not_called()
