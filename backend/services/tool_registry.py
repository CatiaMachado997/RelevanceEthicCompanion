"""
ToolRegistry — dynamic tool loader.

Reads user_tool_connections + tool_definitions from DB and returns
ready-to-invoke LangChain BaseTool instances for the orchestrator.
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, tool as lc_tool
from pydantic import BaseModel, Field

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


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
                    # 1. Fetch active connections
                    cur.execute(
                        """
                        SELECT utc.tool_id, utc.enabled, utc.credentials, utc.mcp_url
                        FROM user_tool_connections utc
                        WHERE utc.user_id = %s AND utc.enabled = TRUE
                        """,
                        (user_id,),
                    )
                    connections = cur.fetchall()

                    if not connections:
                        return []

                    tool_ids = [c["tool_id"] for c in connections]

                    # 2. Fetch definitions
                    cur.execute(
                        """
                        SELECT id, name, description, auth_type, actions
                        FROM tool_definitions
                        WHERE id = ANY(%s) AND enabled = TRUE
                        """,
                        (tool_ids,),
                    )
                    definitions = {row["id"]: row for row in cur.fetchall()}

            tools: list[BaseTool] = []
            conn_by_id = {c["tool_id"]: c for c in connections}

            for tool_id, defn in definitions.items():
                conn_row = conn_by_id[tool_id]
                credentials = conn_row.get("credentials") or {}
                mcp_url = conn_row.get("mcp_url")

                if defn["auth_type"] == "mcp" and mcp_url:
                    mcp_tools = await _load_mcp_tools(tool_id, mcp_url)
                    tools.extend(mcp_tools)
                else:
                    actions = defn.get("actions") or []
                    for action in actions:
                        t = _make_action_tool(
                            tool_id=tool_id,
                            tool_name=defn["name"],
                            action=action,
                            credentials=credentials,
                        )
                        if t:
                            tools.append(t)

            logger.debug(f"ToolRegistry: {len(tools)} tools for user {user_id}")
            return tools

        except Exception as e:
            logger.warning(f"ToolRegistry.get_tools_for_user failed: {e}")
            return []


def _make_action_tool(
    tool_id: str,
    tool_name: str,
    action: dict,
    credentials: dict,
) -> BaseTool | None:
    """
    Build a LangChain BaseTool for a single action on a catalogue tool.
    Returns None for unknown tool_id / action combos (forward-compatible).
    """
    action_name = action.get("name", "")
    action_description = action.get("description", action_name)
    risk_level = action.get("risk_level", "medium")
    unique_name = f"{tool_id}__{action_name}"

    class _DynamicInput(BaseModel):
        params: dict = Field(default_factory=dict, description="Action parameters as key-value pairs")

    class _DynamicTool(BaseTool):
        name: str = unique_name
        description: str = (
            f"{action_description}. "
            f"Tool: {tool_name}. Risk: {risk_level}. "
            "Pass parameters as a dict in the 'params' field."
        )
        args_schema: type[BaseModel] = _DynamicInput
        # Store metadata for ESL gate — accessed via tool.metadata
        metadata: dict = {
            "tool_id": tool_id,
            "action_name": action_name,
            "risk_level": risk_level,
            "credentials": credentials,
        }

        def _run(self, params: dict = None) -> str:  # type: ignore[override]
            raise NotImplementedError("Use async _arun")

        async def _arun(self, params: dict = None) -> str:  # type: ignore[override]
            return await _dispatch_action(
                tool_id=tool_id,
                action_name=action_name,
                params=params or {},
                credentials=credentials,
            )

    return _DynamicTool()


async def _dispatch_action(
    tool_id: str,
    action_name: str,
    params: dict,
    credentials: dict,
) -> str:
    """
    Route an action to the correct connector's execute_action().
    Connector modules are imported lazily to keep startup fast.
    """
    try:
        if tool_id in ("google_calendar_write",):
            from services.connectors.google_calendar import GoogleCalendarConnector
            connector = GoogleCalendarConnector()
        elif tool_id == "gmail_write":
            from services.connectors.gmail import GmailConnector
            connector = GmailConnector()
        elif tool_id == "notion":
            from services.connectors.notion import NotionConnector
            connector = NotionConnector()
        elif tool_id == "slack":
            from services.connectors.slack_write import SlackWriteConnector
            connector = SlackWriteConnector()
        elif tool_id == "github":
            from services.connectors.github import GitHubConnector
            connector = GitHubConnector()
        else:
            return f"Unknown tool: {tool_id}"

        return await connector.execute_action(action_name, params, credentials)
    except Exception as e:
        logger.error(f"Action dispatch failed {tool_id}/{action_name}: {e}")
        return f"Error executing {action_name}: {e}"


async def _load_mcp_tools(tool_id: str, mcp_url: str) -> list[BaseTool]:
    """Load tools from an MCP server URL. Returns [] on connection failure."""
    try:
        from services.mcp_client import MCPClient
        client = MCPClient(mcp_url)
        return await client.get_tools()
    except Exception as e:
        logger.warning(f"MCP tool load failed for {tool_id} @ {mcp_url}: {e}")
        return []
