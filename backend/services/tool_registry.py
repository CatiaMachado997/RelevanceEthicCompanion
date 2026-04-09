"""
ToolRegistry — dynamic tool loader.

Reads user_tool_connections from DB to determine which apps the user has connected,
then returns ready-to-invoke LangChain BaseTool instances:

  • Composio tools  — for catalogue tools (github, notion, slack, gmail_write, google_calendar_write)
  • MCP tools       — for user-supplied MCP server URLs (auth_type='mcp')
"""
from __future__ import annotations

import logging

from langchain_core.tools import BaseTool

from utils.db import get_db_connection

logger = logging.getLogger(__name__)

# Tool IDs that are served via Composio
_COMPOSIO_TOOL_IDS = frozenset({
    "github", "notion", "slack", "gmail_write", "google_calendar_write"
})


class ToolRegistry:
    """Load and instantiate connected tools for a given user."""

    async def get_tools_for_user(self, user_id: str) -> list[BaseTool]:
        """
        Return a list of LangChain BaseTool instances for all tools the user
        has connected. Returns [] on any DB error — never raises.
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT tool_id, mcp_url
                        FROM user_tool_connections
                        WHERE user_id = %s AND enabled = TRUE
                        """,
                        (user_id,),
                    )
                    connections = cur.fetchall()

            if not connections:
                return []

            # Route connections to the appropriate loader
            composio_tool_ids: set[str] = set()
            mcp_connections: list[dict] = []

            for row in connections:
                tid = row["tool_id"]
                if tid in _COMPOSIO_TOOL_IDS:
                    composio_tool_ids.add(tid)
                elif row.get("mcp_url"):
                    mcp_connections.append(row)

            tools: list[BaseTool] = []

            # Load Composio tools
            if composio_tool_ids:
                try:
                    composio_tools = await get_composio_tools_for_user(user_id, composio_tool_ids)
                    tools.extend(composio_tools)
                except Exception as exc:
                    logger.warning(f"Composio tools unavailable for user {user_id}: {exc}")

            # Load MCP tools (keep existing _load_mcp_tools function)
            for row in mcp_connections:
                mcp_tools = await _load_mcp_tools(row["tool_id"], row["mcp_url"])
                tools.extend(mcp_tools)

            logger.debug(f"ToolRegistry: {len(tools)} tools for user {user_id}")
            return tools

        except Exception as e:
            logger.warning(f"ToolRegistry.get_tools_for_user failed: {e}")
            return []


async def get_composio_tools_for_user(user_id: str, connected_tool_ids: set[str]) -> list[BaseTool]:
    """Thin wrapper that delegates to services.composio_tools.

    Kept as a module-level name so tests can patch it via
    ``services.tool_registry.get_composio_tools_for_user``.
    """
    from services.composio_tools import get_composio_tools_for_user as _impl
    return await _impl(user_id, connected_tool_ids)


async def _load_mcp_tools(tool_id: str, mcp_url: str) -> list[BaseTool]:
    """Load tools from an MCP server URL. Returns [] on connection failure.

    Note: MCPClient._wrap_mcp_tool already stamps metadata["tool_id"] = "mcp_custom"
    and metadata["action_name"] = mcp_tool.name on every returned tool, so
    ESLToolGate can identify and gate them without any additional stamping here.
    """
    try:
        from services.mcp_client import MCPClient
        client = MCPClient(mcp_url)
        return await client.get_tools()
    except Exception as e:
        logger.warning(f"MCP tool load failed for {tool_id} @ {mcp_url}: {e}")
        return []
