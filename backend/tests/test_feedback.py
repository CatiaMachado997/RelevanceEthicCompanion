"""Tests for the feedback API endpoint."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from routes.feedback import router as feedback_router, get_feedback_processor
from utils.supabase_auth import get_current_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_app():
    app = FastAPI()
    app.include_router(feedback_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


def make_mock_processor(success: bool = True):
    """Return a mock FeedbackProcessor whose async methods return quickly."""
    mock = MagicMock()
    mock.submit_feedback = AsyncMock(
        return_value={
            "success": success,
            "feedback_id": "mock-feedback-id",
            "message": "Feedback recorded successfully",
        }
    )
    mock.adjust_signal_from_feedback = AsyncMock(return_value=None)
    mock.note_esl_sensitivity_boost = AsyncMock(return_value=None)
    return mock


def test_feedback_submit_thumbs_up(client):
    """POST /api/feedback/ accepts thumbs_up with the correct payload."""
    payload = {
        "item_id": "test-msg-123",
        "item_type": "chat_response",
        "feedback_type": "thumbs_up",
    }
    app = client.app
    app.dependency_overrides[get_feedback_processor] = lambda: make_mock_processor()

    response = client.post("/api/feedback/", json=payload)

    assert response.status_code in (200, 201)
    data = response.json()
    assert data.get("status") in ("ok", "success", "received")


def test_feedback_submit_thumbs_down(client):
    """POST /api/feedback/ accepts thumbs_down."""
    payload = {
        "item_id": "test-msg-456",
        "item_type": "chat_response",
        "feedback_type": "thumbs_down",
    }
    app = client.app
    app.dependency_overrides[get_feedback_processor] = lambda: make_mock_processor()

    response = client.post("/api/feedback/", json=payload)

    assert response.status_code in (200, 201)
    data = response.json()
    assert data.get("status") in ("ok", "success", "received")


def test_feedback_missing_fields_rejected(client):
    """POST /api/feedback/ rejects requests missing required fields."""
    response = client.post("/api/feedback/", json={"item_id": "x"})
    assert response.status_code == 422


def test_feedback_invalid_feedback_type_rejected(client):
    """POST /api/feedback/ rejects unknown feedback_type values."""
    payload = {
        "item_id": "test-msg-789",
        "item_type": "chat_response",
        "feedback_type": "up",  # invalid — must be 'thumbs_up'
    }
    response = client.post("/api/feedback/", json=payload)
    assert response.status_code == 422


def test_feedback_invalid_item_type_rejected(client):
    """POST /api/feedback/ rejects unknown item_type values."""
    payload = {
        "item_id": "test-msg-101",
        "item_type": "unknown_type",
        "feedback_type": "thumbs_up",
    }
    response = client.post("/api/feedback/", json=payload)
    assert response.status_code == 422


def test_feedback_with_additional_notes(client):
    """POST /api/feedback/ accepts optional additional_notes field."""
    payload = {
        "item_id": "test-msg-202",
        "item_type": "chat_response",
        "feedback_type": "thumbs_up",
        "additional_notes": "Very helpful!",
    }
    app = client.app
    app.dependency_overrides[get_feedback_processor] = lambda: make_mock_processor()

    response = client.post("/api/feedback/", json=payload)

    assert response.status_code in (200, 201)
