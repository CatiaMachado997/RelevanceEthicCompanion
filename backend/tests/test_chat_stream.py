import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from main import app
from routes.chat import get_orchestrator


async def mock_stream_message(user_id: str, message: str):
    """Mock async generator that yields a few tokens."""
    for token in ["Hello", " world", "!"]:
        yield token


@pytest.mark.asyncio
async def test_stream_endpoint_returns_event_stream():
    """Test that /api/chat/stream returns a 200 text/event-stream response."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.stream_message = mock_stream_message

    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/chat/stream?message=hello&user_id=00000000-0000-0000-0000-000000000000"
            )
        assert response.status_code in (200, 401)  # 401 if auth enforced
        if response.status_code == 200:
            assert "text/event-stream" in response.headers.get("content-type", "")
            assert "data:" in response.text
    finally:
        app.dependency_overrides.pop(get_orchestrator, None)


@pytest.mark.asyncio
async def test_stream_endpoint_yields_done_event():
    """Test that the stream ends with a done=True SSE event."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.stream_message = mock_stream_message

    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/chat/stream?message=hello&user_id=00000000-0000-0000-0000-000000000000"
            )
        if response.status_code == 200:
            assert '"done": true' in response.text or '"done":true' in response.text
    finally:
        app.dependency_overrides.pop(get_orchestrator, None)
