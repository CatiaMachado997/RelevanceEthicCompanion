"""Tests for multi-agent orchestrator components."""
import pytest
from orchestrator.state import AgentState
from typing import get_type_hints


def test_agent_state_has_messages_field():
    hints = get_type_hints(AgentState)
    assert "messages" in hints, "AgentState must have a 'messages' field"


def test_agent_state_has_active_agent_field():
    hints = get_type_hints(AgentState)
    assert "active_agent" in hints


def test_agent_state_has_agent_outputs_field():
    hints = get_type_hints(AgentState)
    assert "agent_outputs" in hints


from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.checkpoint.memory import MemorySaver


def _mock_llm():
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


def test_research_agent_builds():
    """build_agent returns a compiled graph without raising."""
    from orchestrator.agents.research import build_agent
    checkpointer = MemorySaver()
    agent = build_agent(llm=_mock_llm(), checkpointer=checkpointer)
    assert agent is not None


def test_research_agent_has_tavily_tool():
    from orchestrator.agents.research import build_research_tools
    with patch("orchestrator.agents.research.settings") as mock_settings:
        mock_settings.TAVILY_API_KEY = "test-key"
        tools = build_research_tools(user_id="u1", context_manager=MagicMock())
    names = [t.name for t in tools]
    assert "web_search" in names
