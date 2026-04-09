"""Tests for Composio connect/callback route endpoints."""
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_user_id, get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_app():
    from routes.tool_marketplace import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}


class TestComposioConnectEndpoint:
    def test_returns_connect_url_for_valid_toolkit(self, client, auth_headers):
        """POST /composio/connect with valid toolkit returns connect_url."""
        mock_req = MagicMock()
        mock_req.redirect_url = "https://connect.composio.dev/link/abc"
        mock_session = MagicMock()
        mock_session.authorize.return_value = mock_req
        mock_client_instance = MagicMock()
        mock_client_instance.create.return_value = mock_session

        mock_composio_cls = MagicMock(return_value=mock_client_instance)

        with patch("routes.tool_marketplace.Composio", mock_composio_cls), \
             patch("routes.tool_marketplace.LangchainProvider", MagicMock()), \
             patch("routes.tool_marketplace.settings") as mock_settings, \
             patch("routes.tool_marketplace._build_oauth_state", return_value="signed-state"):
            mock_settings.COMPOSIO_API_KEY = "test-key"
            mock_settings.BACKEND_URL = "http://localhost:8000"
            resp = client.post("/api/tools/composio/connect", json={"toolkit": "github"})

        assert resp.status_code == 200
        assert resp.json()["connect_url"] == "https://connect.composio.dev/link/abc"

    def test_returns_404_for_unknown_toolkit(self, client, auth_headers):
        """POST /composio/connect with unknown toolkit returns 404."""
        with patch("routes.tool_marketplace.settings") as mock_settings:
            mock_settings.COMPOSIO_API_KEY = "test-key"
            resp = client.post("/api/tools/composio/connect", json={"toolkit": "fakeapp"})
        assert resp.status_code == 404

    def test_returns_503_when_api_key_missing(self, client, auth_headers):
        """POST /composio/connect without COMPOSIO_API_KEY returns 503."""
        with patch("routes.tool_marketplace.settings") as mock_settings:
            mock_settings.COMPOSIO_API_KEY = ""
            resp = client.post("/api/tools/composio/connect", json={"toolkit": "github"})
        assert resp.status_code == 503

    def test_returns_502_on_composio_exception(self, client, auth_headers):
        """POST /composio/connect when Composio raises an error returns 502."""
        mock_composio_cls = MagicMock(side_effect=RuntimeError("network error"))

        with patch("routes.tool_marketplace.Composio", mock_composio_cls), \
             patch("routes.tool_marketplace.LangchainProvider", MagicMock()), \
             patch("routes.tool_marketplace.settings") as mock_settings, \
             patch("routes.tool_marketplace._build_oauth_state", return_value="signed-state"):
            mock_settings.COMPOSIO_API_KEY = "test-key"
            mock_settings.BACKEND_URL = "http://localhost:8000"
            resp = client.post("/api/tools/composio/connect", json={"toolkit": "github"})

        assert resp.status_code == 502


class TestComposioCallbackEndpoint:
    def test_success_records_connection_and_redirects(self, client):
        """GET /composio/callback with status=success stores connection and redirects."""
        with patch("routes.tool_marketplace._extract_user_from_state", return_value="user-123"), \
             patch("routes.tool_marketplace._store_connection") as mock_store, \
             patch("routes.tool_marketplace.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            resp = client.get(
                "/api/tools/composio/callback",
                params={
                    "toolkit": "github",
                    "state": "signed-state",
                    "status": "success",
                    "connected_account_id": "ca_abc",
                },
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "connected=github" in resp.headers["location"]
        mock_store.assert_called_once()

        # Verify credentials arg contains the composio_account_id
        call_kwargs = mock_store.call_args.kwargs
        stored_creds = call_kwargs.get("credentials")
        if stored_creds is None:
            # Fall back to positional args: (user_id, tool_id, credentials, ...)
            stored_creds = mock_store.call_args.args[2] if len(mock_store.call_args.args) > 2 else None
        assert stored_creds is not None, "credentials arg not found in mock_store call"
        assert "ca_abc" in stored_creds

    def test_failure_status_redirects_with_error(self, client):
        """GET /composio/callback with status != success redirects with error param."""
        with patch("routes.tool_marketplace.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            resp = client.get(
                "/api/tools/composio/callback",
                params={"toolkit": "github", "state": "state", "status": "error"},
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "error=" in resp.headers["location"]

    def test_missing_status_redirects_with_error(self, client):
        """GET /composio/callback with no status param redirects with error."""
        with patch("routes.tool_marketplace.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            resp = client.get(
                "/api/tools/composio/callback",
                params={"toolkit": "notion", "state": "state"},
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "error=" in resp.headers["location"]

    def test_exception_in_store_redirects_with_error(self, client):
        """GET /composio/callback when _store_connection raises redirects with error."""
        with patch("routes.tool_marketplace._extract_user_from_state", return_value="user-123"), \
             patch("routes.tool_marketplace._store_connection", side_effect=RuntimeError("db down")), \
             patch("routes.tool_marketplace.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            resp = client.get(
                "/api/tools/composio/callback",
                params={
                    "toolkit": "github",
                    "state": "signed-state",
                    "status": "success",
                    "connected_account_id": "ca_abc",
                },
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "error=" in resp.headers["location"]
