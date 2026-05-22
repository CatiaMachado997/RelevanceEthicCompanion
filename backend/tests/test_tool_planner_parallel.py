"""Sprint I Task 13: integration test for parallel actions within one step."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.state import AgentState
from orchestrator.nodes.tools import tool_execution_node


def _base_state(**overrides) -> AgentState:
    state: AgentState = {
        "user_id": "u-1",
        "message": "what was on my calendar the week of the M-KOPA email?",
        "conversation_id": "c-1",
        "model": "llama-3.3-70b-versatile",
        "user_context": {},
        "conversation_history": [],
        "active_sources": [],
        "intent": "chat",
        "tool_calls": [],
        "tool_results": [],
        "esl_decision": None,
        "proposed_content": "",
        "response_text": "",
        "response_events": [],
        "citations": [],
        "document_sources": [],
        "token_count": 0,
        "token_warning": None,
        "pending_tool_confirmation": None,
        "source_context": [],
        "force_retrieval": False,
        "planner_step": 1,
        "max_planner_steps": 3,
        "plan_steps": [
            {
                "step": 1,
                "thought": "I need both the email and the calendar.",
                "actions": [
                    {"tool": "search_documents", "params": {"query": "M-KOPA"}},
                    {"tool": "query_calendar", "params": {"days_back": 30}},
                ],
                "observations": [],
                "started_at": "2026-05-20T12:00:00+00:00",
            }
        ],
        "planner_run_id": "run-1",
    }
    state.update(overrides)
    return state


def _mk_synth_llm():
    """Patch target for ChatGroq — returns an object whose .ainvoke returns a content-bearing mock."""
    inner = MagicMock()
    inner.ainvoke = AsyncMock(return_value=MagicMock(content="OK done."))
    inner.bind_tools = MagicMock(return_value=inner)
    return MagicMock(return_value=inner)


@pytest.mark.asyncio
async def test_two_independent_actions_run_in_parallel():
    """Both actions complete; latency reflects parallelism."""
    import time

    async def slow_docs(_p):
        await asyncio.sleep(0.1)
        return [{"chunk_uuid": "u1", "snippet": "m-kopa"}]

    async def slow_cal(_p):
        await asyncio.sleep(0.1)
        return [{"title": "Standup", "start": "2026-04-20T09:00"}]

    docs_tool = MagicMock()
    docs_tool.name = "search_documents"
    docs_tool.ainvoke = slow_docs
    docs_tool.metadata = {}
    cal_tool = MagicMock()
    cal_tool.name = "query_calendar"
    cal_tool.ainvoke = slow_cal
    cal_tool.metadata = {}

    with patch(
        "orchestrator.nodes.tools.get_context_manager",
        MagicMock(return_value=MagicMock()),
    ), patch(
        "services.langchain_tools.create_langchain_tools",
        AsyncMock(return_value=[docs_tool, cal_tool]),
    ), patch(
        "orchestrator.nodes.tools._record_telemetry", MagicMock(),
    ), patch(
        "langchain_groq.ChatGroq", _mk_synth_llm(),
    ):
        started = time.perf_counter()
        result = await tool_execution_node(_base_state())
        elapsed = time.perf_counter() - started

    tool_names = {r["tool"] for r in result["tool_results"]}
    assert tool_names == {"search_documents", "query_calendar"}
    # Two 100 ms sleeps in parallel should net ~100 ms, not 200 ms.
    # Generous bound: parallelism is real if < 180 ms.
    assert elapsed < 0.18, f"expected parallel (<180ms), got {elapsed*1000:.0f}ms"
    # Observations attached to the step
    assert len(result["plan_steps"][-1]["observations"]) == 2
    # All observations are status=ok
    statuses = [o["status"] for o in result["plan_steps"][-1]["observations"]]
    assert statuses == ["ok", "ok"]


@pytest.mark.asyncio
async def test_one_action_fails_other_succeeds_step_proceeds():
    """When one of two parallel actions fails, the other's result still lands."""

    async def fail_docs(_p):
        raise RuntimeError("documents unavailable")

    async def ok_cal(_p):
        return [{"title": "Standup"}]

    docs_tool = MagicMock()
    docs_tool.name = "search_documents"
    docs_tool.ainvoke = fail_docs
    docs_tool.metadata = {}
    cal_tool = MagicMock()
    cal_tool.name = "query_calendar"
    cal_tool.ainvoke = ok_cal
    cal_tool.metadata = {}

    with patch(
        "orchestrator.nodes.tools.get_context_manager",
        MagicMock(return_value=MagicMock()),
    ), patch(
        "services.langchain_tools.create_langchain_tools",
        AsyncMock(return_value=[docs_tool, cal_tool]),
    ), patch(
        "orchestrator.nodes.tools._record_telemetry", MagicMock(),
    ), patch(
        "langchain_groq.ChatGroq", _mk_synth_llm(),
    ):
        result = await tool_execution_node(_base_state())

    obs = result["plan_steps"][-1]["observations"]
    statuses = sorted(o["status"] for o in obs)
    assert statuses == ["error", "ok"]
    # Failed action's attempts should be 2 (one retry)
    failed = next(o for o in obs if o["status"] == "error")
    assert failed["attempts"] == 2
