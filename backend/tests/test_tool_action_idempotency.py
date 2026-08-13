"""Regression coverage for side-effecting tool action idempotency."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.nodes.tools import _execute_action_once
from services.tool_action_idempotency import ActionClaim, build_action_key


def test_action_key_is_stable_across_parameter_order():
    common = {
        "user_id": "user-1",
        "conversation_id": "conv-1",
        "planner_run_id": "run-1",
        "step_index": 2,
        "action_index": 1,
        "tool_name": "create_note",
    }
    first = build_action_key(tool_input={"content": "x", "as_goal": False}, **common)
    second = build_action_key(tool_input={"as_goal": False, "content": "x"}, **common)
    assert first == second


def test_request_id_keeps_key_stable_across_replanning():
    common = {
        "user_id": "user-1",
        "conversation_id": "conv-1",
        "tool_name": "send_email",
        "tool_input": {"to": "person@example.com", "body": "hello"},
        "request_id": "request-1",
    }
    first = build_action_key(
        planner_run_id="run-1", step_index=1, action_index=0, **common
    )
    second = build_action_key(
        planner_run_id="run-2", step_index=3, action_index=2, **common
    )
    assert first == second


def test_request_id_deduplicates_goal_when_replan_adds_description():
    common = {
        "user_id": "user-1",
        "conversation_id": "conv-1",
        "planner_run_id": "run-1",
        "tool_name": "create_goal",
        "request_id": "request-1",
    }
    first = build_action_key(
        tool_input={
            "title": "Wake up at 6am",
            "description": "Wake up at 6am every day",
            "priority": 5,
        },
        step_index=1,
        action_index=0,
        **common,
    )
    second = build_action_key(
        tool_input={
            "title": "  WAKE   UP AT 6AM ",
            "description": None,
            "priority": 5,
        },
        step_index=2,
        action_index=0,
        **common,
    )

    assert first == second


@pytest.mark.asyncio
async def test_write_action_executes_once_and_records_success():
    tool = MagicMock(name="tool")
    tool.name = "create_note"
    tool.ainvoke = AsyncMock(return_value="saved")
    ledger = MagicMock()
    ledger.claim.return_value = ActionClaim(claimed=True, status="started")

    with patch(
        "services.tool_action_idempotency.ToolActionIdempotencyService",
        return_value=ledger,
    ):
        result = await _execute_action_once(
            tool=tool,
            params={"content": "remember"},
            category="write-personal",
            user_id="user-1",
            conversation_id="conv-1",
            planner_run_id="run-1",
            step_index=1,
            action_index=0,
        )

    assert result["status"] == "ok"
    assert result["attempts"] == 1
    tool.ainvoke.assert_awaited_once()
    ledger.finish.assert_called_once()
    assert ledger.finish.call_args.kwargs["status"] == "success"


@pytest.mark.asyncio
async def test_write_action_replays_success_without_calling_tool():
    tool = MagicMock(name="tool")
    tool.name = "create_note"
    tool.ainvoke = AsyncMock()
    ledger = MagicMock()
    ledger.claim.return_value = ActionClaim(
        claimed=False, status="success", output="already saved"
    )

    with patch(
        "services.tool_action_idempotency.ToolActionIdempotencyService",
        return_value=ledger,
    ):
        result = await _execute_action_once(
            tool=tool,
            params={"content": "remember"},
            category="write-personal",
            user_id="user-1",
            conversation_id="conv-1",
            planner_run_id="run-1",
            step_index=1,
            action_index=0,
        )

    assert result["result"] == "already saved"
    assert result["idempotent_replay"] is True
    tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_write_error_is_not_automatically_retried():
    tool = MagicMock(name="tool")
    tool.name = "send_email"
    tool.ainvoke = AsyncMock(side_effect=RuntimeError("response lost"))
    ledger = MagicMock()
    ledger.claim.return_value = ActionClaim(claimed=True, status="started")

    with patch(
        "services.tool_action_idempotency.ToolActionIdempotencyService",
        return_value=ledger,
    ):
        result = await _execute_action_once(
            tool=tool,
            params={"to": "person@example.com"},
            category="write-external",
            user_id="user-1",
            conversation_id="conv-1",
            planner_run_id="run-1",
            step_index=1,
            action_index=0,
        )

    assert result["status"] == "error"
    assert result["attempts"] == 1
    assert result["error_code"] == "action_outcome_uncertain"
    assert result["retryable"] is False
    tool.ainvoke.assert_awaited_once()
    assert ledger.finish.call_args.kwargs["status"] == "uncertain"


@pytest.mark.asyncio
async def test_read_error_remains_retryable():
    tool = MagicMock(name="tool")
    tool.name = "query_calendar"
    tool.ainvoke = AsyncMock(
        side_effect=[RuntimeError("temporary"), [{"title": "Standup"}]]
    )
    result = await _execute_action_once(
        tool=tool,
        params={},
        category="read-personal",
        user_id="user-1",
        conversation_id="conv-1",
        planner_run_id="run-1",
        step_index=1,
        action_index=0,
    )
    assert result["status"] == "ok"
    assert result["attempts"] == 2
