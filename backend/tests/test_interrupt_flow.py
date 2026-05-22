"""Sprint J Task 16: tool_execution_node calls interrupt() for user-flagged tools.

Each sub-test verifies one resolution path (approve / skip / cancel / trust)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.state import AgentState
from orchestrator.nodes.tools import tool_execution_node


USER_ID = "00000000-0000-0000-0000-000000000000"


def _state_with_calendar_action() -> AgentState:
    state: AgentState = {
        "user_id": USER_ID,
        "message": "what's on my calendar?",
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
        "plan_steps": [{
            "step": 1,
            "thought": "I need to check the calendar.",
            "actions": [{"tool": "query_calendar", "params": {"days_back": 7}}],
            "observations": [],
            "started_at": "2026-05-20T12:00:00+00:00",
        }],
        "planner_run_id": "run-1",
    }
    return state


def _mk_tool(name, category, return_value):
    t = MagicMock()
    t.name = name
    t.category = category
    t.metadata = {}
    t.ainvoke = AsyncMock(return_value=return_value)
    return t


def _mk_synth_llm():
    inner = MagicMock()
    inner.ainvoke = AsyncMock(return_value=MagicMock(content="OK"))
    inner.bind_tools = MagicMock(return_value=inner)
    return MagicMock(return_value=inner)



@pytest.mark.asyncio
async def test_interrupt_fires_when_tool_in_per_tool_prefs():
    """If safety_prefs.should_confirm returns True, interrupt() is called and
    its payload includes the expected fields."""
    cal = _mk_tool("query_calendar", "read-personal", [{"title": "Standup"}])

    captured: dict = {}

    def fake_interrupt(payload):
        captured.update(payload)
        return {"action": "approve"}

    fake_prefs = MagicMock()
    fake_prefs.should_confirm = MagicMock(return_value=True)
    fake_prefs.explain_reason = MagicMock(
        return_value="tool 'query_calendar' is set to ask before running"
    )

    with patch("orchestrator.nodes.tools._j_settings") as flag, \
         patch("orchestrator.nodes.tools.SafetyPreferencesService") as PrefsCls, \
         patch("orchestrator.nodes.tools.get_context_manager",
               MagicMock(return_value=MagicMock())), \
         patch("services.langchain_tools.create_langchain_tools",
               AsyncMock(return_value=[cal])), \
         patch("orchestrator.nodes.tools._record_telemetry", MagicMock()), \
         patch("langchain_groq.ChatGroq", _mk_synth_llm()), \
         patch("langgraph.types.interrupt", side_effect=fake_interrupt):
        flag.STREAMING_REASONING_ENABLED = True
        PrefsCls.return_value.load_for_user.return_value = fake_prefs

        result = await tool_execution_node(_state_with_calendar_action())

    assert captured.get("kind") == "user_confirmation"
    assert captured.get("tool") == "query_calendar"
    assert captured.get("category") == "read-personal"
    # approve fell through → action actually ran
    assert any(r["tool"] == "query_calendar" for r in result["tool_results"])


@pytest.mark.asyncio
async def test_skip_decision_marks_observation_and_continues():
    cal = _mk_tool("query_calendar", "read-personal", [{"title": "Standup"}])
    fake_prefs = MagicMock()
    fake_prefs.should_confirm = MagicMock(return_value=True)
    fake_prefs.explain_reason = MagicMock(return_value="x")

    with patch("orchestrator.nodes.tools._j_settings") as flag, \
         patch("orchestrator.nodes.tools.SafetyPreferencesService") as PrefsCls, \
         patch("orchestrator.nodes.tools.get_context_manager",
               MagicMock(return_value=MagicMock())), \
         patch("services.langchain_tools.create_langchain_tools",
               AsyncMock(return_value=[cal])), \
         patch("orchestrator.nodes.tools._record_telemetry", MagicMock()), \
         patch("langchain_groq.ChatGroq", _mk_synth_llm()), \
         patch("langgraph.types.interrupt", return_value={"action": "skip"}):
        flag.STREAMING_REASONING_ENABLED = True
        PrefsCls.return_value.load_for_user.return_value = fake_prefs

        result = await tool_execution_node(_state_with_calendar_action())

    obs = result["plan_steps"][-1]["observations"]
    assert obs and obs[0]["status"] == "skipped"
    cal.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_decision_aborts_step():
    cal = _mk_tool("query_calendar", "read-personal", [{"title": "Standup"}])
    fake_prefs = MagicMock()
    fake_prefs.should_confirm = MagicMock(return_value=True)
    fake_prefs.explain_reason = MagicMock(return_value="x")

    with patch("orchestrator.nodes.tools._j_settings") as flag, \
         patch("orchestrator.nodes.tools.SafetyPreferencesService") as PrefsCls, \
         patch("orchestrator.nodes.tools.get_context_manager",
               MagicMock(return_value=MagicMock())), \
         patch("services.langchain_tools.create_langchain_tools",
               AsyncMock(return_value=[cal])), \
         patch("orchestrator.nodes.tools._record_telemetry", MagicMock()), \
         patch("langchain_groq.ChatGroq", _mk_synth_llm()), \
         patch("langgraph.types.interrupt", return_value={"action": "cancel"}):
        flag.STREAMING_REASONING_ENABLED = True
        PrefsCls.return_value.load_for_user.return_value = fake_prefs

        result = await tool_execution_node(_state_with_calendar_action())

    obs = result["plan_steps"][-1]["observations"]
    assert obs and obs[0]["status"] == "cancelled"
    cal.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_trust_decision_deletes_per_tool_row():
    cal = _mk_tool("query_calendar", "read-personal", [{"title": "Standup"}])
    fake_prefs = MagicMock()
    fake_prefs.should_confirm = MagicMock(return_value=True)
    fake_prefs.explain_reason = MagicMock(return_value="x")

    with patch("orchestrator.nodes.tools._j_settings") as flag, \
         patch("orchestrator.nodes.tools.SafetyPreferencesService") as PrefsCls, \
         patch("orchestrator.nodes.tools.get_context_manager",
               MagicMock(return_value=MagicMock())), \
         patch("services.langchain_tools.create_langchain_tools",
               AsyncMock(return_value=[cal])), \
         patch("orchestrator.nodes.tools._record_telemetry", MagicMock()), \
         patch("langchain_groq.ChatGroq", _mk_synth_llm()), \
         patch("langgraph.types.interrupt",
               return_value={"action": "approve", "trust": True}):
        flag.STREAMING_REASONING_ENABLED = True
        PrefsCls.return_value.load_for_user.return_value = fake_prefs

        await tool_execution_node(_state_with_calendar_action())

    PrefsCls.return_value.delete_tool.assert_called_once_with(
        USER_ID, tool_name="query_calendar"
    )
