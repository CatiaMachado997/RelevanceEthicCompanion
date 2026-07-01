"""Sprint D Task 2: TaskDependenciesService tests.

All tests use a mocked DB cursor — no live Postgres required.
"""

from unittest.mock import MagicMock, patch

import pytest


TASK_A = "11111111-1111-1111-1111-111111111111"
TASK_B = "22222222-2222-2222-2222-222222222222"
TASK_C = "33333333-3333-3333-3333-333333333333"


def _mock_db(cur: MagicMock):
    """Build a get_db_connection() context manager that yields a conn whose
    cursor() context manager yields `cur`."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    db_ctx = MagicMock()
    db_ctx.__enter__.return_value = conn
    db_ctx.__exit__.return_value = False
    return db_ctx, conn


@patch("services.task_dependencies.get_db_connection")
def test_add_dependency_inserts_row(mock_get_db):
    from services.task_dependencies import TaskDependenciesService

    cur = MagicMock()
    # Cycle check returns None → no cycle
    cur.fetchone.return_value = None
    db_ctx, conn = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = TaskDependenciesService()
    svc.add_dependency(TASK_A, TASK_B)

    # Two execute calls: cycle check + insert
    assert cur.execute.call_count == 2
    insert_call = cur.execute.call_args_list[1]
    sql = insert_call.args[0]
    params = insert_call.args[1]
    assert "INSERT INTO task_dependencies" in sql
    assert params == (TASK_A, TASK_B)
    conn.commit.assert_called_once()


@patch("services.task_dependencies.get_db_connection")
def test_add_dependency_rejects_self(mock_get_db):
    from services.task_dependencies import TaskDependenciesService

    svc = TaskDependenciesService()
    with pytest.raises(ValueError, match="cannot depend on itself"):
        svc.add_dependency(TASK_A, TASK_A)

    # No DB call at all — guard runs before connection is acquired
    mock_get_db.assert_not_called()


@patch("services.task_dependencies.get_db_connection")
def test_add_dependency_rejects_cycle(mock_get_db):
    from services.task_dependencies import TaskDependenciesService

    cur = MagicMock()
    # Cycle-check CTE returns a row → adding A->B would create a cycle
    cur.fetchone.return_value = {"?column?": 1}
    db_ctx, conn = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = TaskDependenciesService()
    with pytest.raises(ValueError, match="cycle"):
        svc.add_dependency(TASK_A, TASK_B)

    # Only the cycle-check executed, no INSERT.
    assert cur.execute.call_count == 1
    executed_sql = cur.execute.call_args_list[0].args[0]
    assert "RECURSIVE reachable" in executed_sql
    conn.commit.assert_not_called()


@patch("services.task_dependencies.get_db_connection")
def test_get_blockers_returns_transitive_chain(mock_get_db):
    from services.task_dependencies import TaskDependenciesService

    cur = MagicMock()
    # Three blockers at increasing depth — order preserved by service.
    cur.fetchall.return_value = [
        {"task_id": TASK_B, "title": "Direct blocker", "status": "in_progress", "depth": 1},
        {"task_id": TASK_C, "title": "Indirect blocker", "status": "todo", "depth": 2},
        {"task_id": "44444444-4444-4444-4444-444444444444", "title": "Deep blocker", "status": "todo", "depth": 3},
    ]
    db_ctx, _ = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = TaskDependenciesService()
    result = svc.get_blockers(TASK_A)

    assert len(result) == 3
    assert [r["depth"] for r in result] == [1, 2, 3]
    assert result[0]["task_id"] == TASK_B
    assert result[1]["title"] == "Indirect blocker"

    sql = cur.execute.call_args.args[0]
    assert "RECURSIVE blockers" in sql
    assert cur.execute.call_args.args[1] == (TASK_A,)
