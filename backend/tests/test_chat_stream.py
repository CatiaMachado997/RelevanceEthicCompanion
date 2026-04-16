"""
Tests for GET /api/chat/stream (SSE streaming endpoint).

The endpoint now always uses stream_langgraph (USE_LANGGRAPH=True by default).
Tests mock orchestrator.graph.stream_langgraph to avoid real DB/LLM calls.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch


async def mock_stream_langgraph(
    user_id, message, model=None, conversation_id=None, **kwargs
):
    """Mock async generator yielding token + done events."""
    yield {"event": "token", "token": "Hello"}
    yield {"event": "token", "token": " world"}
    yield {"event": "token", "token": "!"}
    yield {"event": "done", "esl_decision": None}


@pytest.mark.asyncio
async def test_stream_endpoint_returns_event_stream():
    """GET /api/chat/stream returns 200 text/event-stream when authenticated in dev mode."""
    from main import app
    from config import settings

    with patch(
        "orchestrator.graph.stream_langgraph", side_effect=mock_stream_langgraph
    ), patch.object(settings, "AUTH_ENFORCEMENT_ENABLED", False), patch.object(
        settings, "ENVIRONMENT", "development"
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/chat/stream?message=hello")

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "data:" in response.text


@pytest.mark.asyncio
async def test_stream_endpoint_yields_token_events():
    """Streaming response body contains token events."""
    from main import app
    from config import settings

    with patch(
        "orchestrator.graph.stream_langgraph", side_effect=mock_stream_langgraph
    ), patch.object(settings, "AUTH_ENFORCEMENT_ENABLED", False), patch.object(
        settings, "ENVIRONMENT", "development"
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/chat/stream?message=hello")

    assert '"event": "token"' in response.text or '"event":"token"' in response.text


@pytest.mark.asyncio
async def test_stream_endpoint_ends_with_done_event():
    """Streaming response ends with a done event."""
    from main import app
    from config import settings

    with patch(
        "orchestrator.graph.stream_langgraph", side_effect=mock_stream_langgraph
    ), patch.object(settings, "AUTH_ENFORCEMENT_ENABLED", False), patch.object(
        settings, "ENVIRONMENT", "development"
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/chat/stream?message=hello")

    assert '"event": "done"' in response.text or '"event":"done"' in response.text
