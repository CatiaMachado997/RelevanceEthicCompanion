import pytest
from unittest.mock import patch, MagicMock


def _make_connection_row(tool_id, mcp_url=None):
    return {
        "tool_id": tool_id,
        "enabled": True,
        "credentials": {"access_token": "tok"},
        "mcp_url": mcp_url,
    }


def _make_definition_row(tool_id, actions=None, auth_type="oauth"):
    return {
        "id": tool_id,
        "name": tool_id.capitalize(),
        "description": "A tool",
        "auth_type": auth_type,
        "actions": actions or [{"name": "read", "description": "Read", "risk_level": "low"}],
    }


@pytest.mark.asyncio
async def test_get_tools_for_user_returns_only_connected():
    """Only tools with active user_tool_connections are returned."""
    from services.tool_registry import ToolRegistry

    registry = ToolRegistry()
    with patch("services.tool_registry.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Only github is connected
        cur.fetchall.side_effect = [
            [_make_connection_row("github")],
            [_make_definition_row("github", actions=[
                {"name": "list_issues", "description": "List open issues", "risk_level": "low"}
            ])],
        ]
        mock_db.return_value = conn

        tools = await registry.get_tools_for_user("user-1")

    assert len(tools) == 1
    assert tools[0].name == "github__list_issues"


@pytest.mark.asyncio
async def test_get_tools_for_user_empty_when_none_connected():
    """Returns [] when user has no tool connections."""
    from services.tool_registry import ToolRegistry

    registry = ToolRegistry()
    with patch("services.tool_registry.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchall.return_value = []
        mock_db.return_value = conn

        tools = await registry.get_tools_for_user("user-1")

    assert tools == []


@pytest.mark.asyncio
async def test_get_tools_returns_empty_on_db_error():
    """Returns [] gracefully when DB is unavailable."""
    from services.tool_registry import ToolRegistry

    registry = ToolRegistry()
    with patch("services.tool_registry.get_db_connection", side_effect=Exception("DB down")):
        tools = await registry.get_tools_for_user("user-1")

    assert tools == []
