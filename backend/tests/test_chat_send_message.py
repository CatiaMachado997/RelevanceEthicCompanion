from fastapi.testclient import TestClient
from fastapi import FastAPI # Import FastAPI
from services.orchestrator import Orchestrator
from routes.chat import get_orchestrator, router as chat_router # Import the router directly
from unittest.mock import MagicMock
import pytest

# Create a mock orchestrator
mock_orchestrator = MagicMock(spec=Orchestrator)

def get_mock_orchestrator():
    return mock_orchestrator

# Create a test FastAPI app instance
test_app = FastAPI()
test_app.dependency_overrides[get_orchestrator] = get_mock_orchestrator
test_app.include_router(chat_router)

client = TestClient(test_app)

@pytest.fixture(autouse=True)
def reset_mock():
    """Reset the mock before each test."""
    mock_orchestrator.reset_mock()

def test_send_message_approved():
    """Test sending a message that gets approved by the ESL."""
    # Configure the mock
    mock_orchestrator.handle_user_message.return_value = {
        "message": "Hello",
        "response": "Hi there!",
        "executed": True,
        "esl_decision": {"status": "APPROVED", "reason": "All good."},
        "transparency": "Action approved."
    }

    # Make the request
    response = client.post("/api/chat/", json={"message": "Hello"})

    # Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Hi there!"
    assert data["executed"] is True
    assert data["esl_decision"]["status"] == "APPROVED"

def test_send_message_vetoed():
    """Test sending a message that gets vetoed by the ESL."""
    # Configure the mock
    mock_orchestrator.handle_user_message.return_value = {
        "message": "Tell me something sensitive",
        "response": None,
        "executed": False,
        "esl_decision": {"status": "VETOED", "reason": "Violates privacy."},
        "transparency": "Action blocked."
    }

    # Make the request
    response = client.post("/api/chat/", json={"message": "Tell me something sensitive"})

    # Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["response"] is None
    assert data["executed"] is False
    assert data["esl_decision"]["status"] == "VETOED"

def test_send_message_error():
    """Test an error during message processing."""
    # Configure the mock
    mock_orchestrator.handle_user_message.side_effect = Exception("Something went wrong")

    # Make the request
    response = client.post("/api/chat/", json={"message": "This will error"})

    # Assert the response
    assert response.status_code == 500
    assert "Error processing message: Something went wrong" in response.json()["detail"]
