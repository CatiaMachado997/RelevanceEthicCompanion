"""Tests for true LangGraph streaming via astream_events()."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_stream_langgraph_yields_tokens():
    """stream_langgraph() should yield token events before the done event."""
    from orchestrator.graph import stream_langgraph

    received = []
    async for event in stream_langgraph(
        user_id="test-user",
        message="Hello",
        model="llama-3.3-70b-versatile",
    ):
        received.append(event)

    event_types = [e.get("event") for e in received]
    # Must contain at least one token and exactly one done
    assert "token" in event_types, f"No token events received: {event_types}"
    assert event_types.count("done") == 1, f"Expected exactly one done: {event_types}"
    # done must be last
    assert event_types[-1] == "done", f"done must be last: {event_types}"


@pytest.mark.asyncio
async def test_stream_langgraph_done_has_esl_key():
    """The done event must include an esl_decision key."""
    from orchestrator.graph import stream_langgraph

    done_event = None
    async for event in stream_langgraph(user_id="test-user", message="Test"):
        if event.get("event") == "done":
            done_event = event

    assert done_event is not None
    assert "esl_decision" in done_event


@pytest.mark.asyncio
async def test_stream_langgraph_no_double_done():
    """Only one done event should be yielded."""
    from orchestrator.graph import stream_langgraph

    done_count = 0
    async for event in stream_langgraph(user_id="test-user", message="Count done events"):
        if event.get("event") == "done":
            done_count += 1

    assert done_count == 1


def test_response_formatter_node_no_fake_chunks():
    """response_formatter_node should not produce fake token chunks."""
    import asyncio
    from orchestrator.nodes.response import response_formatter_node
    from unittest.mock import MagicMock
    from esl.models import ESLDecisionStatus

    mock_decision = MagicMock()
    mock_decision.status = ESLDecisionStatus.APPROVED
    mock_decision.reason = "approved"
    mock_decision.violated_values = []

    state = {
        "esl_decision": mock_decision,
        "proposed_content": "Hello world this is a test response",
    }

    result = asyncio.run(response_formatter_node(state))
    events = result.get("response_events", [])

    token_events = [e for e in events if e.get("event") == "token"]
    # No fake token chunks — actual tokens come via astream_events
    assert len(token_events) == 0, f"response_formatter should not produce token events: {token_events}"

    done_events = [e for e in events if e.get("event") == "done"]
    assert len(done_events) == 1
