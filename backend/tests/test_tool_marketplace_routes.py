import pytest
from unittest.mock import patch, MagicMock, AsyncMock, ANY
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


def make_db_mock(mock_db, fetchall_result=None, fetchone_result=None):
    """Configure mock_db (patched get_db_connection) as a context manager and return (conn, cur)."""
    cur = MagicMock()
    cur.fetchall.return_value = fetchall_result or []
    cur.fetchone.return_value = fetchone_result
    cur.rowcount = 1  # default: one row affected

    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    mock_db.return_value = conn
    return conn, cur


def test_get_catalogue_returns_tools(client):
    """GET /api/tools returns all enabled tool definitions."""
    with patch("routes.tool_marketplace.get_db_connection") as mock_db:
        conn, cur = make_db_mock(
            mock_db,
            fetchall_result=[
                {
                    "id": "github",
                    "name": "GitHub",
                    "description": "Issues and PRs",
                    "auth_type": "oauth",
                    "actions": [],
                    "icon_url": None,
                    "enabled": True,
                }
            ],
        )
        resp = client.get("/api/tools")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["id"] == "github"


def test_get_connected_returns_user_tools(client):
    """GET /api/tools/connected returns user's active connections."""
    with patch("routes.tool_marketplace.get_db_connection") as mock_db:
        conn, cur = make_db_mock(
            mock_db,
            fetchall_result=[
                {
                    "tool_id": "github",
                    "enabled": True,
                    "connected_at": "2026-04-08T00:00:00+00:00",
                    "last_used_at": None,
                    "mcp_url": None,
                    "name": "GitHub",
                    "description": "Issues",
                    "auth_type": "oauth",
                    "actions": [],
                    "icon_url": None,
                }
            ],
        )
        resp = client.get("/api/tools/connected")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["tool_id"] == "github"


def test_set_permission_upserts_trust(client):
    """POST /api/tools/{tool_id}/permissions upserts trust_level."""
    with patch("routes.tool_marketplace.ESLToolGate") as MockGate:
        mock_gate = MagicMock()
        mock_gate.set_trust = AsyncMock()
        MockGate.return_value = mock_gate

        resp = client.post(
            "/api/tools/github/permissions",
            json={"action_name": "create_issue", "trust_level": "allow"},
        )

    assert resp.status_code == 200
    mock_gate.set_trust.assert_called_once_with(
        user_id=ANY,
        tool_id="github",
        action_name="create_issue",
        trust_level="allow",
    )


def test_disconnect_tool_returns_404_when_not_connected(client):
    """DELETE /api/tools/{tool_id}/disconnect returns 404 if no row deleted."""
    with patch("routes.tool_marketplace.get_db_connection") as mock_db:
        conn, cur = make_db_mock(mock_db)
        cur.rowcount = 0  # no rows deleted

        resp = client.delete("/api/tools/github/disconnect")

    assert resp.status_code == 404


def test_revoke_permission_returns_404_when_not_found(client):
    """DELETE /api/tools/{tool_id}/permissions/{action} returns 404 if not found."""
    with patch("routes.tool_marketplace.get_db_connection") as mock_db:
        conn, cur = make_db_mock(mock_db)
        cur.rowcount = 0

        resp = client.delete("/api/tools/github/permissions/create_issue")

    assert resp.status_code == 404


def test_connect_tool_returns_500_on_unsupported_auth_type(client):
    """POST /api/tools/{tool_id}/connect raises 500 for unknown auth_type."""
    with patch("routes.tool_marketplace.get_db_connection") as mock_db:
        conn, cur = make_db_mock(mock_db)
        cur.fetchone.return_value = {"auth_type": "magic_beans"}

        resp = client.post("/api/tools/github/connect", json={})

    assert resp.status_code == 500


def test_mcp_connect_rejects_non_http_url(client):
    """POST /api/tools/mcp rejects non-HTTP URLs (SSRF protection)."""
    resp = client.post("/api/tools/mcp", json={"mcp_url": "file:///etc/passwd"})
    assert resp.status_code == 422
