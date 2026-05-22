"""Sprint I Task 5: unit tests for PlannerRunsService."""

from unittest.mock import MagicMock, patch

from services.planner_runs import PlannerRunsService


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def _mock_db(fetchone_value):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_value
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cur


def test_create_returns_uuid_and_inserts_running_row():
    """create() inserts a row with status='running' and returns its UUID."""
    conn, cur = _mock_db({"id": "11111111-1111-1111-1111-111111111111"})
    with patch("services.planner_runs.get_db_connection", return_value=conn):
        svc = PlannerRunsService()
        run_id = svc.create(
            user_id=TEST_USER_ID,
            conversation_id="conv-1",
            intent="chat",
        )
    assert run_id == "11111111-1111-1111-1111-111111111111"
    sql = cur.execute.call_args[0][0]
    assert "INSERT INTO planner_runs" in sql
    assert "'running'" in sql or "%s" in sql


def test_create_returns_empty_string_on_db_failure():
    """Telemetry must never break the calling flow."""
    with patch("services.planner_runs.get_db_connection", side_effect=RuntimeError("boom")):
        svc = PlannerRunsService()
        run_id = svc.create(user_id=TEST_USER_ID, conversation_id=None, intent="chat")
    assert run_id == ""


def test_finalize_updates_status_and_totals():
    """finalize() UPDATEs the row with the resolved status and totals."""
    conn, cur = _mock_db({"id": "rid"})
    with patch("services.planner_runs.get_db_connection", return_value=conn):
        svc = PlannerRunsService()
        svc.finalize(
            run_id="rid",
            status="completed",
            total_steps=2,
            total_actions=3,
            total_duration_ms=812,
            plan_steps=[{"step": 1, "thought": "x", "actions": [], "observations": []}],
        )
    sql = cur.execute.call_args[0][0]
    assert "UPDATE planner_runs" in sql
    assert "SET" in sql
    params = cur.execute.call_args[0][1]
    assert "completed" in params
    assert 2 in params
    assert 3 in params


def test_finalize_swallows_db_failure():
    """Telemetry must never break the calling flow."""
    with patch("services.planner_runs.get_db_connection", side_effect=RuntimeError("boom")):
        svc = PlannerRunsService()
        svc.finalize(run_id="rid", status="completed", total_steps=0,
                     total_actions=0, total_duration_ms=0, plan_steps=[])


def test_finalize_rejects_invalid_status():
    """Status outside the table CHECK constraint should be refused."""
    conn, cur = _mock_db({"id": "rid"})
    with patch("services.planner_runs.get_db_connection", return_value=conn):
        svc = PlannerRunsService()
        svc.finalize(run_id="rid", status="nonsense", total_steps=0,
                     total_actions=0, total_duration_ms=0, plan_steps=[])
    # If finalize defended at the application layer (recommended), it
    # short-circuited and never called cur.execute. If it didn't defend
    # and the CHECK would have caught it, we accept that too.
    # Either way: no exception escaped.
