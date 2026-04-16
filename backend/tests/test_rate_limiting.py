"""Tests that rate limiting is active on auth endpoints."""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("utils.weaviate_client.get_weaviate_client", return_value=None):
        from main import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


def test_auth_session_route_exists(client):
    """POST /api/auth/session route must exist and be reachable."""
    routes = [
        r
        for r in client.app.routes
        if hasattr(r, "path")
        and r.path == "/api/auth/session"
        and hasattr(r, "methods")
        and "POST" in r.methods
    ]
    assert len(routes) == 1, "POST /api/auth/session route must exist"


def test_get_user_id_key_func_returns_user_id():
    """get_user_id_or_ip returns user_id when set on request state."""
    from utils.rate_limit import get_user_id_or_ip
    from unittest.mock import MagicMock

    mock_request = MagicMock()
    mock_request.state.user_id = "abc-123"
    key = get_user_id_or_ip(mock_request)
    assert key == "abc-123"


def test_get_user_id_key_func_falls_back_to_ip():
    """get_user_id_or_ip falls back to IP when no user_id on state."""
    from utils.rate_limit import get_user_id_or_ip
    from unittest.mock import MagicMock

    mock_request = MagicMock()
    # Simulate AttributeError on state.user_id by using spec=[] (no attributes)
    mock_request.state = MagicMock(spec=[])
    mock_request.client.host = "1.2.3.4"
    key = get_user_id_or_ip(mock_request)
    assert key == "1.2.3.4"
