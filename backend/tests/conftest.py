"""Shared pytest fixtures for the backend test suite."""

import os

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def pytest_collection_modifyitems(config, items):
    """Skip tests marked `integration` unless RUN_INTEGRATION_TESTS=1 is set."""
    if os.environ.get("RUN_INTEGRATION_TESTS") == "1":
        return
    skip_integration = pytest.mark.skip(
        reason="Integration test — set RUN_INTEGRATION_TESTS=1 to run"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


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
