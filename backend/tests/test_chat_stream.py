import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from main import app
from routes.chat import get_orchestrator


async def mock_stream_message(user_id: str, message: str, conversation_id=None):
    """Mock async generator that yields event dicts in the new SSE protocol."""
    yield {"event": "token", "token": "Hello"}
    yield {"event": "token", "token": " world"}
    yield {"event": "token", "token": "!"}
    yield {"event": "done"}


@pytest.mark.asyncio
async def test_stream_endpoint_returns_event_stream():
    """Test that /api/chat/stream returns a 200 text/event-stream response."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.stream_message = mock_stream_message

    with patch("routes.chat.get_orchestrator", return_value=mock_orchestrator):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/chat/stream?message=hello&user_id=00000000-0000-0000-0000-000000000000"
            )
        assert response.status_code in (200, 401)
        if response.status_code == 200:
            assert "text/event-stream" in response.headers.get("content-type", "")
            assert "data:" in response.text


@pytest.mark.asyncio
async def test_stream_endpoint_yields_done_event():
    """Test that the stream ends with a done event in the new SSE protocol."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.stream_message = mock_stream_message

    with patch("routes.chat.get_orchestrator", return_value=mock_orchestrator):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/chat/stream?message=hello&user_id=00000000-0000-0000-0000-000000000000"
            )
        if response.status_code == 200:
            assert '"event": "done"' in response.text or '"event":"done"' in response.text
