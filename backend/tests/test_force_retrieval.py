"""Tests for the `/ask` slash-command path: force_retrieval injects a
search_documents tool call regardless of the planner LLM's choice."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

USER_ID = "00000000-0000-0000-0000-000000000000"


def _base_state(**overrides) -> dict:
    state = {
        "user_id": USER_ID,
        "message": "what does the report say?",
        "conversation_id": None,
        "model": "llama-3.3-70b-versatile",
        "user_context": {},
        "conversation_history": [],
        "active_sources": [],
        "intent": "",
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
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
@patch("services.langchain_tools.create_langchain_tools")
@patch("langchain_groq.ChatGroq")
@patch("orchestrator.nodes.tools.get_context_manager")
async def test_force_retrieval_injects_search_documents(
    mock_cm, mock_groq_cls, mock_create_tools
):
    """When state.force_retrieval=True and the planner LLM proposes no tool
    call, the planner node still injects a `search_documents` call so the
    `/ask` slash command always grounds against documents."""
    from orchestrator.nodes.tools import tool_planner_node

    mock_cm.return_value = MagicMock()
    mock_create_tools.return_value = []

    fake_response = MagicMock()
    fake_response.tool_calls = []
    fake_response.content = "Sure, here's an answer without tools."
    llm_with_tools = MagicMock()
    llm_with_tools.ainvoke = AsyncMock(return_value=fake_response)
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm_with_tools)
    mock_groq_cls.return_value = llm

    out = await tool_planner_node(_base_state(force_retrieval=True))

    assert len(out["tool_calls"]) == 1
    tc = out["tool_calls"][0]
    assert tc["name"] == "search_documents"
    assert tc["args"]["query"] == "what does the report say?"
    assert tc["args"]["k"] == 5
    # When we forcibly inject a tool call we must clear proposed_content so the
    # graph routes through tool_execution instead of straight to ESL.
    assert out["proposed_content"] == ""


@pytest.mark.asyncio
@patch("services.langchain_tools.create_langchain_tools")
@patch("langchain_groq.ChatGroq")
@patch("orchestrator.nodes.tools.get_context_manager")
async def test_force_retrieval_bypasses_provider_tool_selection(
    mock_cm, mock_groq_cls, mock_create_tools
):
    """Explicit retrieval is deterministic even if provider tool calls are flaky."""
    from orchestrator.nodes.tools import tool_planner_node

    mock_cm.return_value = MagicMock()
    mock_create_tools.return_value = []

    existing_call = {
        "name": "search_documents",
        "args": {"query": "report", "k": 3},
        "id": "call_abc",
    }
    fake_response = MagicMock()
    fake_response.tool_calls = [existing_call]
    fake_response.content = ""
    llm_with_tools = MagicMock()
    llm_with_tools.ainvoke = AsyncMock(return_value=fake_response)
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm_with_tools)
    mock_groq_cls.return_value = llm

    out = await tool_planner_node(_base_state(force_retrieval=True))

    assert len(out["tool_calls"]) == 1
    assert out["tool_calls"][0]["id"] == "forced_search_documents"
    llm_with_tools.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
@patch("services.langchain_tools.create_langchain_tools")
@patch("langchain_groq.ChatGroq")
@patch("orchestrator.nodes.tools.get_context_manager")
async def test_force_retrieval_contextualizes_pronoun_followup(
    mock_cm, mock_groq_cls, mock_create_tools
):
    from orchestrator.nodes.tools import tool_planner_node

    mock_cm.return_value = MagicMock()
    mock_create_tools.return_value = []
    mock_groq_cls.return_value = MagicMock()

    out = await tool_planner_node(
        _base_state(
            force_retrieval=True,
            message="What about its documentation?",
            conversation_history=[
                {
                    "role": "user",
                    "content": "Explain obligations for a high-risk AI system.",
                },
                {"role": "assistant", "content": "Here is a summary."},
            ],
        )
    )

    query = out["tool_calls"][0]["args"]["query"]
    assert "high-risk AI system" in query
    assert query.endswith("Current follow-up: What about its documentation?")


@pytest.mark.asyncio
@patch("services.langchain_tools.create_langchain_tools")
@patch("langchain_groq.ChatGroq")
@patch("orchestrator.nodes.tools.get_context_manager")
async def test_no_force_retrieval_leaves_planner_alone(
    mock_cm, mock_groq_cls, mock_create_tools
):
    """force_retrieval=False (default chat) — planner output is untouched."""
    from orchestrator.nodes.tools import tool_planner_node

    mock_cm.return_value = MagicMock()
    mock_create_tools.return_value = []

    fake_response = MagicMock()
    fake_response.tool_calls = []
    fake_response.content = "Hi there."
    llm_with_tools = MagicMock()
    llm_with_tools.ainvoke = AsyncMock(return_value=fake_response)
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm_with_tools)
    mock_groq_cls.return_value = llm

    out = await tool_planner_node(_base_state(force_retrieval=False))

    assert out["tool_calls"] == []
    assert out["proposed_content"] == "Hi there."
