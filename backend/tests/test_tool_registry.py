"""
Tests for the refactored ToolRegistry.

Old tests for _make_action_tool / _dispatch_action are removed — those
functions no longer exist.  New tests verify the Composio + MCP routing.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_connection_row(tool_id, mcp_url=None):
    return {
        "tool_id": tool_id,
        "enabled": True,
        "mcp_url": mcp_url,
    }


def _mock_db(rows):
    """Return a patched get_db_connection context manager that yields *rows*."""
    conn = MagicMock()
    cur = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = rows
    return conn


def _mock_tool(name="mock_tool"):
    t = MagicMock()
    t.name = name
    return t


# ---------------------------------------------------------------------------
# TestToolRegistryWithComposio
# ---------------------------------------------------------------------------

class TestToolRegistryWithComposio:

    @pytest.mark.asyncio
    async def test_routes_composio_tool_ids_to_composio(self):
        """github/notion/etc. tool_ids must go to get_composio_tools_for_user."""
        from services.tool_registry import ToolRegistry

        fake_tool = _mock_tool("github__list_issues")
        registry = ToolRegistry()

        conn = _mock_db([_make_connection_row("github")])

        with patch("services.tool_registry.get_db_connection", return_value=conn), \
             patch(
                 "services.tool_registry.get_composio_tools_for_user",
                 new=AsyncMock(return_value=[fake_tool]),
             ) as mock_composio:

            tools = await registry.get_tools_for_user("user-1")

        mock_composio.assert_called_once_with("user-1", {"github"})
        assert fake_tool in tools

    @pytest.mark.asyncio
    async def test_routes_mcp_connections_to_mcp_loader(self):
        """Rows with mcp_url must go to _load_mcp_tools."""
        from services.tool_registry import ToolRegistry

        fake_tool = _mock_tool("mcp_custom_tool")
        registry = ToolRegistry()

        conn = _mock_db([
            _make_connection_row("mcp_custom", mcp_url="http://localhost:9000"),
        ])

        with patch("services.tool_registry.get_db_connection", return_value=conn), \
             patch(
                 "services.tool_registry._load_mcp_tools",
                 new=AsyncMock(return_value=[fake_tool]),
             ) as mock_mcp:

            tools = await registry.get_tools_for_user("user-1")

        mock_mcp.assert_called_once_with("mcp_custom", "http://localhost:9000")
        assert fake_tool in tools

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_connections(self):
        """Returns [] when user has no tool connections."""
        from services.tool_registry import ToolRegistry

        registry = ToolRegistry()
        conn = _mock_db([])

        with patch("services.tool_registry.get_db_connection", return_value=conn):
            tools = await registry.get_tools_for_user("user-1")

        assert tools == []

    @pytest.mark.asyncio
    async def test_composio_failure_returns_partial_not_raises(self):
        """Composio failure must not prevent MCP tools from loading."""
        from services.tool_registry import ToolRegistry

        mcp_tool = _mock_tool("mcp_fallback_tool")
        registry = ToolRegistry()

        conn = _mock_db([
            _make_connection_row("github"),
            _make_connection_row("mcp_custom", mcp_url="http://localhost:9000"),
        ])

        with patch("services.tool_registry.get_db_connection", return_value=conn), \
             patch(
                 "services.tool_registry.get_composio_tools_for_user",
                 new=AsyncMock(side_effect=RuntimeError("Composio down")),
             ), \
             patch(
                 "services.tool_registry._load_mcp_tools",
                 new=AsyncMock(return_value=[mcp_tool]),
             ):

            tools = await registry.get_tools_for_user("user-1")

        # MCP tool must still be present despite Composio failure
        assert mcp_tool in tools

    @pytest.mark.asyncio
    async def test_get_tools_returns_empty_on_db_error(self):
        """Returns [] gracefully when DB is unavailable."""
        from services.tool_registry import ToolRegistry

        registry = ToolRegistry()
        with patch("services.tool_registry.get_db_connection", side_effect=Exception("DB down")):
            tools = await registry.get_tools_for_user("user-1")

        assert tools == []

    @pytest.mark.asyncio
    async def test_both_composio_and_mcp_loaded_together(self):
        """User with both Composio and MCP connections gets tools from both."""
        from services.tool_registry import ToolRegistry

        composio_tool = _mock_tool("notion__create_page")
        mcp_tool = _mock_tool("mcp_custom_tool")
        registry = ToolRegistry()

        conn = _mock_db([
            _make_connection_row("notion"),
            _make_connection_row("mcp_custom", mcp_url="http://localhost:9000"),
        ])

        with patch("services.tool_registry.get_db_connection", return_value=conn), \
             patch(
                 "services.tool_registry.get_composio_tools_for_user",
                 new=AsyncMock(return_value=[composio_tool]),
             ), \
             patch(
                 "services.tool_registry._load_mcp_tools",
                 new=AsyncMock(return_value=[mcp_tool]),
             ):

            tools = await registry.get_tools_for_user("user-1")

        assert composio_tool in tools
        assert mcp_tool in tools
        assert len(tools) == 2
