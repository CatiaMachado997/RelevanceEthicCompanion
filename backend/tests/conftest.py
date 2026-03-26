"""Shared pytest fixtures for the backend test suite."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def test_client():
    """Return a TestClient for the FastAPI app with external services mocked."""
    # Patch Weaviate so the app starts even when Docker is not running
    mock_weaviate = MagicMock()
    mock_weaviate.is_ready.return_value = True

    with patch("utils.weaviate_client.get_weaviate_client", return_value=None):
        from main import app
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
