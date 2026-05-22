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
