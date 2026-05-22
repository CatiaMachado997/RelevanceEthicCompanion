"""Sprint K Task 6: integration test — tool_planner_node prepends a
SystemMessage when PlannerRunMemoryService.recall() returns matches."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.state import AgentState
from orchestrator.nodes.tools import tool_planner_node
from services.planner_run_memory import PastRun


USER_ID = "00000000-0000-0000-0000-000000000000"


def _base_state() -> AgentState:
    state: AgentState = {
        "user_id": USER_ID,
        "message": "what's on my calendar this week?",
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
        "planner_step": 0,
        "max_planner_steps": 3,
        "plan_steps": [],
        "planner_run_id": None,
    }
    return state


@pytest.mark.asyncio
async def test_planner_prepends_memory_system_message_when_recall_hits():
    """When EPISODIC_MEMORY_ENABLED and recall returns matches, the planner
    LLM is invoked with a SystemMessage whose content includes the past
    plan summaries."""
    fake_past = [
        PastRun(
            planner_run_id="run-a",
            message_text="what was on my calendar last week",
            plan_summary="query_calendar (completed in 0.4s, 1 step)",
            similarity=0.81,
        ),
    ]

    captured_messages: list = []

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        resp = MagicMock()
        resp.content = "I have enough."
        resp.tool_calls = []
        return resp

    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = fake_ainvoke

    with patch("orchestrator.nodes.tools._j_settings") as flag, \
         patch("orchestrator.nodes.tools.get_context_manager",
               MagicMock(return_value=MagicMock())), \
         patch("services.langchain_tools.create_langchain_tools",
               AsyncMock(return_value=[])), \
         patch("orchestrator.nodes.tools.PlannerRunMemoryService") as MemCls, \
         patch("services.planner_runs.PlannerRunsService") as RunsCls, \
         patch("langchain_groq.ChatGroq", return_value=llm):
        flag.STREAMING_REASONING_ENABLED = False
        flag.EPISODIC_MEMORY_ENABLED = True
        flag.EPISODIC_MEMORY_TOP_K = 3
        flag.EPISODIC_MEMORY_MIN_SIMILARITY = 0.6
        flag.EPISODIC_MEMORY_MAX_AGE_DAYS = 90
        MemCls.return_value.recall = AsyncMock(return_value=fake_past)
        RunsCls.return_value.create = MagicMock(return_value="run-new")

        result = await tool_planner_node(_base_state())

    contents = [getattr(m, "content", "") for m in captured_messages]
    assert any(
        "handled similar questions" in (c or "").lower()
        for c in contents
    ), f"missing memory SystemMessage; saw: {contents[:3]}"
    assert any("query_calendar" in (c or "") for c in contents)

    ps = result.get("plan_steps") or []
    assert ps, "plan_steps missing"
    first = ps[0]
    assert first.get("memory_used"), f"memory_used not folded into step; first step: {first}"


@pytest.mark.asyncio
async def test_planner_skips_memory_when_flag_off():
    """When EPISODIC_MEMORY_ENABLED is False, recall is not called and no
    SystemMessage is prepended."""
    captured_messages: list = []

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        resp = MagicMock()
        resp.content = "ok"
        resp.tool_calls = []
        return resp

    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = fake_ainvoke

    mem_cls = MagicMock()
    mem_cls.return_value.recall = AsyncMock(return_value=[])

    with patch("orchestrator.nodes.tools._j_settings") as flag, \
         patch("orchestrator.nodes.tools.get_context_manager",
               MagicMock(return_value=MagicMock())), \
         patch("services.langchain_tools.create_langchain_tools",
               AsyncMock(return_value=[])), \
         patch("orchestrator.nodes.tools.PlannerRunMemoryService", mem_cls), \
         patch("services.planner_runs.PlannerRunsService") as RunsCls, \
         patch("langchain_groq.ChatGroq", return_value=llm):
        flag.STREAMING_REASONING_ENABLED = False
        flag.EPISODIC_MEMORY_ENABLED = False
        flag.EPISODIC_MEMORY_TOP_K = 3
        flag.EPISODIC_MEMORY_MIN_SIMILARITY = 0.6
        flag.EPISODIC_MEMORY_MAX_AGE_DAYS = 90
        RunsCls.return_value.create = MagicMock(return_value="run-new")

        await tool_planner_node(_base_state())

    mem_cls.return_value.recall.assert_not_called()
    contents = [getattr(m, "content", "") for m in captured_messages]
    assert not any(
        "handled similar questions" in (c or "").lower() for c in contents
    )
