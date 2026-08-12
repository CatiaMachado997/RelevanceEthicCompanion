"""DeepEval regression suite for retries, replay, and confirmations."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip(
    "deepeval",
    reason="DeepEval is installed only with requirements-evals.txt",
)

from deepeval import assert_test, log_hyperparameters
from deepeval.test_case import LLMTestCase

from orchestrator.nodes.tools import _execute_action_once
from routes.chat import _pending_interrupt_payload
from services.tool_action_idempotency import ActionClaim
from tests.evals.metrics import ToolActionReliabilityMetric

SCENARIOS = [
    "read-transient-retry",
    "write-timeout-no-auto-retry",
    "write-success-replay",
    "confirmation-recovered-after-refresh",
    "partial-read-failure-remains-actionable",
]


@log_hyperparameters
def tool_action_eval_hyperparameters():
    return {
        "suite": "tool-action-reliability",
        "scenario_count": len(SCENARIOS),
        "write_auto_retry": False,
        "durable_confirmation": True,
    }


async def _execute(scenario: str) -> tuple[dict, dict]:
    tool = MagicMock()
    common = {
        "params": {"value": "x"},
        "user_id": "user-1",
        "conversation_id": "conv-1",
        "planner_run_id": "run-1",
        "step_index": 1,
        "action_index": 0,
        "request_id": "request-1",
    }
    if scenario == "read-transient-retry":
        tool.name = "query_calendar"
        tool.ainvoke = AsyncMock(side_effect=[RuntimeError("temporary"), "events"])
        result = await _execute_action_once(
            tool=tool, category="read-personal", **common
        )
        return {
            "status": result["status"],
            "attempts": result["attempts"],
            "calls": tool.ainvoke.await_count,
        }, {"status": "ok", "attempts": 2, "calls": 2}

    if scenario == "write-timeout-no-auto-retry":
        tool.name = "send_email"
        tool.ainvoke = AsyncMock(side_effect=TimeoutError("provider timeout"))
        ledger = MagicMock()
        ledger.claim.return_value = ActionClaim(claimed=True, status="started")
        with patch(
            "services.tool_action_idempotency.ToolActionIdempotencyService",
            return_value=ledger,
        ):
            result = await _execute_action_once(
                tool=tool, category="write-external", **common
            )
        return {
            "status": result["status"],
            "attempts": result["attempts"],
            "calls": tool.ainvoke.await_count,
            "retryable": result["retryable"],
            "error_code": result["error_code"],
        }, {
            "status": "error",
            "attempts": 1,
            "calls": 1,
            "retryable": False,
            "error_code": "action_outcome_uncertain",
        }

    if scenario == "write-success-replay":
        tool.name = "create_note"
        tool.ainvoke = AsyncMock()
        ledger = MagicMock()
        ledger.claim.return_value = ActionClaim(
            claimed=False, status="success", output="saved"
        )
        with patch(
            "services.tool_action_idempotency.ToolActionIdempotencyService",
            return_value=ledger,
        ):
            result = await _execute_action_once(
                tool=tool, category="write-personal", **common
            )
        return {
            "status": result["status"],
            "calls": tool.ainvoke.await_count,
            "idempotent_replay": result["idempotent_replay"],
        }, {"status": "ok", "calls": 0, "idempotent_replay": True}

    if scenario == "confirmation-recovered-after-refresh":
        interrupt = MagicMock(value={"tool": "send_email", "action_index": 0})
        snapshot = MagicMock(tasks=(MagicMock(interrupts=(interrupt,)),))
        payload = _pending_interrupt_payload(snapshot)
        return {
            "paused": bool(payload),
            "tool": payload.get("tool"),
        }, {"paused": True, "tool": "send_email"}

    tool.name = "web_search"
    tool.ainvoke = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    result = await _execute_action_once(tool=tool, category="read-external", **common)
    return {
        "status": result["status"],
        "attempts": result["attempts"],
        "retryable": result["retryable"],
    }, {"status": "error", "attempts": 2, "retryable": True}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_tool_action_reliability(scenario: str):
    actual, expected = asyncio.run(_execute(scenario))
    test_case = LLMTestCase(
        input=scenario,
        actual_output=json.dumps(actual, sort_keys=True),
        expected_output=json.dumps(expected, sort_keys=True),
    )
    assert_test(test_case=test_case, metrics=[ToolActionReliabilityMetric()])
