"""
Regression tests for the chat streaming interface.
These tests define the contract that the LangGraph orchestrator must satisfy.
Run against orchestrator_v2 first (baseline), then against LangGraph orchestrator.
"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from main import app


async def _collect_stream_events(response_text: str) -> list[dict]:
    """Parse SSE data lines into a list of event dicts."""
    events = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


async def mock_stream(*args, **kwargs):
    yield {"event": "token", "token": "Hello"}
    yield {"event": "token", "token": " world"}
    yield {"event": "done"}


# Helper — must be defined before any test that calls it
def base_state() -> dict:
    return {
        "user_id": "u1", "message": "", "conversation_id": None, "model": "llama",
        "user_context": {}, "conversation_history": [], "intent": "",
        "tool_calls": [], "tool_results": [], "esl_decision": None,
        "proposed_content": "", "response_text": "", "response_events": [],
        "token_count": 0, "token_warning": None,
        "pending_tool_confirmation": None,
        "source_context": [],
        "active_sources": [],
    }


@pytest.mark.asyncio
async def test_stream_returns_200_event_stream():
    """Chat stream endpoint returns 200 with text/event-stream content type."""
    from config import settings
    with patch("orchestrator.graph.stream_langgraph", side_effect=mock_stream), \
         patch.object(settings, "AUTH_ENFORCEMENT_ENABLED", False), \
         patch.object(settings, "ENVIRONMENT", "development"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/chat/stream?message=hello")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_stream_emits_token_events():
    """Stream yields token events followed by a done event."""
    from config import settings
    with patch("orchestrator.graph.stream_langgraph", side_effect=mock_stream), \
         patch.object(settings, "AUTH_ENFORCEMENT_ENABLED", False), \
         patch.object(settings, "ENVIRONMENT", "development"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/chat/stream?message=hello")
    events = await _collect_stream_events(r.text)
    token_events = [e for e in events if e.get("event") == "token"]
    done_events = [e for e in events if e.get("event") == "done"]
    assert len(token_events) >= 1
    assert len(done_events) == 1
    assert done_events[-1] == events[-1]  # done is last


@pytest.mark.asyncio
async def test_stream_token_events_have_token_field():
    """Every token event has a non-empty 'token' string field."""
    from config import settings
    with patch("orchestrator.graph.stream_langgraph", side_effect=mock_stream), \
         patch.object(settings, "AUTH_ENFORCEMENT_ENABLED", False), \
         patch.object(settings, "ENVIRONMENT", "development"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/chat/stream?message=hello")
    events = await _collect_stream_events(r.text)
    for e in events:
        if e.get("event") == "token":
            assert isinstance(e.get("token"), str)
            assert len(e["token"]) > 0


@pytest.mark.asyncio
async def test_stream_missing_message_returns_422():
    """Request without message param returns 422 Unprocessable Entity."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/chat/stream?user_id=00000000-0000-0000-0000-000000000000")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_context_builder_populates_state():
    """ContextBuilder node adds user_context and conversation_history to state."""
    from orchestrator.nodes.context import context_builder_node
    from unittest.mock import AsyncMock

    mock_cm = MagicMock()
    mock_cm.get_user_context = AsyncMock(return_value=MagicMock(
        active_goals=[], user_values=[], focus_mode=False,
        additional_context={}
    ))
    mock_cm.get_conversation_history = AsyncMock(return_value=[])
    mock_cm.get_recent_source_items = AsyncMock(return_value=[])

    state = {
        "user_id": "test-user", "message": "hello", "conversation_id": None,
        "model": "llama", "user_context": {}, "conversation_history": [],
        "intent": "", "tool_calls": [], "tool_results": [],
        "esl_decision": None, "proposed_content": "", "response_text": "",
        "response_events": [], "token_count": 0, "token_warning": None,
    }
    with patch("orchestrator.nodes.context.get_context_manager", return_value=mock_cm):
        result = await context_builder_node(state)
    assert "user_context" in result
    assert "conversation_history" in result
    assert "source_context" in result


@pytest.mark.asyncio
async def test_intent_classifier_chat():
    from orchestrator.nodes.intent import intent_classifier_node
    state = {**base_state(), "message": "what should I focus on today?"}
    result = await intent_classifier_node(state)
    assert result["intent"] == "chat"

@pytest.mark.asyncio
async def test_intent_classifier_search():
    from orchestrator.nodes.intent import intent_classifier_node
    state = {**base_state(), "message": "/search latest AI news"}
    result = await intent_classifier_node(state)
    assert result["intent"] == "search"

@pytest.mark.asyncio
async def test_intent_classifier_plan():
    from orchestrator.nodes.intent import intent_classifier_node
    state = {**base_state(), "message": "/plan launch campaign next quarter"}
    result = await intent_classifier_node(state)
    assert result["intent"] == "plan"

@pytest.mark.asyncio
async def test_esl_gateway_approved():
    from orchestrator.nodes.esl import esl_gateway_node
    from esl.models import ESLDecision, ESLDecisionStatus
    mock_decision = ESLDecision(
        status=ESLDecisionStatus.APPROVED, reason="OK",
        violated_values=[], applied_rules=[], confidence=0.95
    )
    mock_esl = MagicMock()
    mock_esl.evaluate_action = AsyncMock(return_value=mock_decision)
    state = {**base_state(), "proposed_content": "Here is your summary.", "user_context": {}}
    with patch("orchestrator.nodes.esl.get_esl", return_value=mock_esl):
        result = await esl_gateway_node(state)
    assert result["esl_decision"].status == ESLDecisionStatus.APPROVED


@pytest.mark.asyncio
async def test_stream_via_langgraph_path():
    """Regression: stream endpoint always uses LangGraph (USE_LANGGRAPH=True is default)."""
    from config import settings

    async def mock_langgraph(*args, **kwargs):
        yield {"event": "token", "token": "Hello"}
        yield {"event": "done"}

    with patch("orchestrator.graph.stream_langgraph", side_effect=mock_langgraph), \
         patch.object(settings, "AUTH_ENFORCEMENT_ENABLED", False), \
         patch.object(settings, "ENVIRONMENT", "development"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/chat/stream?message=hello")
    assert r.status_code == 200
    events = await _collect_stream_events(r.text)
    assert any(e.get("event") == "done" for e in events)
