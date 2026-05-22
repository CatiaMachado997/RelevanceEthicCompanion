"""Sprint C Task 2: ToolTelemetryService tests.

All tests use a mocked DB cursor — no live Postgres required.
"""

import logging
from unittest.mock import MagicMock, patch

USER_ID = "11111111-1111-1111-1111-111111111111"
EVENT_ID = "22222222-2222-2222-2222-222222222222"


def _mock_db(cur: MagicMock):
    """Build a get_db_connection() context manager that yields a conn whose
    cursor() context manager yields ``cur``."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    db_ctx = MagicMock()
    db_ctx.__enter__.return_value = conn
    db_ctx.__exit__.return_value = False
    return db_ctx, conn


@patch("services.tool_telemetry.get_db_connection")
def test_record_tool_call_inserts_row(mock_get_db):
    from services.tool_telemetry import ToolTelemetryService

    cur = MagicMock()
    cur.fetchone.return_value = {"id": EVENT_ID}
    db_ctx, conn = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = ToolTelemetryService()
    returned = svc.record_tool_call(
        user_id=USER_ID,
        tool_name="search_documents",
        source="chat",
        source_ref="conv-abc",
        input={"query": "ethics"},
        output={"results": [{"id": "doc1"}]},
        status="success",
        latency_ms=42,
    )

    assert returned == EVENT_ID
    assert cur.execute.call_count == 1
    call = cur.execute.call_args
    sql, params = call.args[0], call.args[1]
    assert "INSERT INTO tool_call_events" in sql
    assert "RETURNING id" in sql
    # Positional params in declared order.
    assert params[0] == USER_ID
    assert params[1] == "search_documents"
    assert params[2] == "chat"
    assert params[3] == "conv-abc"
    # JSONB columns are json.dumps strings.
    assert isinstance(params[4], str) and '"query"' in params[4]
    assert isinstance(params[5], str) and '"results"' in params[5]
    assert params[6] == "success"
    assert params[7] is None  # error_message
    assert params[8] is None  # esl_decision
    assert params[9] == 42  # latency_ms
    conn.commit.assert_called_once()


@patch("services.tool_telemetry.get_db_connection")
def test_record_tool_call_swallows_db_error(mock_get_db, caplog):
    from services.tool_telemetry import ToolTelemetryService

    cur = MagicMock()
    cur.execute.side_effect = RuntimeError("connection reset")
    db_ctx, _ = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = ToolTelemetryService()
    with caplog.at_level(logging.WARNING, logger="services.tool_telemetry"):
        returned = svc.record_tool_call(
            user_id=USER_ID,
            tool_name="create_task",
            source="chat",
            source_ref=None,
            input={"title": "x"},
            output=None,
            status="error",
            error_message="boom",
        )

    assert returned == ""
    assert any("failed to record tool call" in rec.message for rec in caplog.records)


@patch("services.tool_telemetry.get_db_connection")
def test_list_tool_calls_filters_by_tool_name(mock_get_db):
    from services.tool_telemetry import ToolTelemetryService

    cur = MagicMock()
    cur.fetchall.return_value = [
        {
            "id": EVENT_ID,
            "user_id": USER_ID,
            "tool_name": "search_documents",
            "source": "chat",
            "source_ref": "conv-1",
            "input": {"query": "x"},
            "output": {"ok": True},
            "status": "success",
            "error_message": None,
            "esl_decision": None,
            "latency_ms": 10,
            "created_at": None,
        }
    ]
    db_ctx, _ = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = ToolTelemetryService()
    result = svc.list_tool_calls(USER_ID, tool_name="search_documents", limit=25)

    assert len(result) == 1
    assert result[0]["tool_name"] == "search_documents"

    sql, params = cur.execute.call_args.args[0], cur.execute.call_args.args[1]
    assert "FROM tool_call_events" in sql
    assert "tool_name = %s" in sql
    assert "ORDER BY created_at DESC" in sql
    # user_id, tool_name, then limit (no source/since filters).
    assert params == (USER_ID, "search_documents", 25)


def test_record_tool_call_persists_planner_run_breadcrumbs():
    """Sprint I Task 7: record_tool_call accepts planner_run_id, step_index, action_index."""
    from services.tool_telemetry import ToolTelemetryService

    cur = MagicMock()
    cur.fetchone.return_value = {"id": "row-uuid"}
    db_ctx, _ = _mock_db(cur)
    with patch("services.tool_telemetry.get_db_connection", return_value=db_ctx):
        svc = ToolTelemetryService()
        svc.record_tool_call(
            user_id="user-1",
            tool_name="search_documents",
            source="chat",
            source_ref="conv-1",
            input={"q": "x"},
            output={"r": 1},
            status="success",
            latency_ms=42,
            planner_run_id="run-1",
            step_index=1,
            action_index=0,
        )
    sql = cur.execute.call_args[0][0]
    params = cur.execute.call_args[0][1]
    assert "planner_run_id" in sql
    assert "step_index" in sql
    assert "action_index" in sql
    assert "run-1" in params
    assert 1 in params
    assert 0 in params
