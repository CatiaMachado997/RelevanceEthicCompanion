"""
Tests for POST /api/chat/ (non-streaming endpoint).

The endpoint now collects events from stream_langgraph() and returns a ChatResponse.
Tests mock orchestrator.graph.stream_langgraph to avoid real DB/LLM calls.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.chat import router as chat_router
from utils.supabase_auth import get_current_user_id
from unittest.mock import patch, AsyncMock
import pytest

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_app():
    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


async def _fake_stream_approved(*args, **kwargs):
    """Yields token + done events simulating an approved ESL response."""
    yield {"event": "token", "token": "Hi there!"}
    yield {"event": "done", "esl_decision": None}


async def _fake_stream_empty(*args, **kwargs):
    """Yields only a done event with no tokens — simulates a vetoed/empty response."""
    yield {"event": "done", "esl_decision": None}


async def _fake_stream_error(*args, **kwargs):
    raise RuntimeError("Something went wrong")
    yield  # pragma: no cover — makes this an async generator so async-for works


def test_send_message_returns_200_with_response(client):
    """A successful stream yields a response text and executed=True."""
    with patch("orchestrator.graph.stream_langgraph", side_effect=_fake_stream_approved):
        response = client.post("/api/chat/", json={"message": "Hello"})
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Hi there!"
    assert data["executed"] is True
    assert data["esl_decision"]["status"] == "APPROVED"


def test_send_message_returns_empty_response_when_no_tokens(client):
    """When no token events arrive, response is None and executed=False."""
    with patch("orchestrator.graph.stream_langgraph", side_effect=_fake_stream_empty):
        response = client.post("/api/chat/", json={"message": "silent"})
    assert response.status_code == 200
    data = response.json()
    assert data["response"] is None
    assert data["executed"] is False


def test_send_message_returns_500_on_stream_error(client):
    """If stream_langgraph raises, the endpoint returns 500."""
    with patch("orchestrator.graph.stream_langgraph", side_effect=_fake_stream_error):
        response = client.post("/api/chat/", json={"message": "This will error"})
    assert response.status_code == 500
    assert "Something went wrong" in response.json()["detail"]


def test_send_message_requires_auth():
    """POST /api/chat/ returns 401 when auth enforcement is active."""
    from config import settings
    app = FastAPI()
    app.include_router(chat_router)
    unauthenticated_client = TestClient(app, raise_server_exceptions=False)
    with patch.object(settings, "AUTH_ENFORCEMENT_ENABLED", True), \
         patch.object(settings, "ENVIRONMENT", "production"):
        response = unauthenticated_client.post("/api/chat/", json={"message": "hello"})
    assert response.status_code == 401
