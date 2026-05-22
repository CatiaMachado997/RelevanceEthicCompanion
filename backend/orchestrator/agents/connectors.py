"""ConnectorsAgent — Composio-managed integrations (Slack, Gmail, GitHub, Notion)."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Connectors Agent. You interact with the user's connected apps "
    "(Slack, Gmail, GitHub, Notion) only when explicitly authorised. "
    "Before taking any write action (send message, create issue, etc.), "
    "confirm the action with the user. Never act without confirmation on destructive operations."
)


def build_connector_tools(user_id: str, connected_tool_ids: set[str]) -> list[BaseTool]:
    if not getattr(settings, "COMPOSIO_API_KEY", None):
        return []

    try:
        from services.composio_tools import get_composio_tools_for_user
        import asyncio
        tools = asyncio.get_event_loop().run_until_complete(
            get_composio_tools_for_user(
                user_id=user_id,
                connected_tool_ids=connected_tool_ids,
            )
        )
        return tools or []
    except Exception as e:
        logger.warning(f"Could not load Composio tools: {e}")
        return []


def build_agent(
    llm: Any,
    checkpointer: Any,
    user_id: str = "",
    connected_tool_ids: set[str] | None = None,
):
    """Return a compiled ConnectorsAgent graph."""
    tools = build_connector_tools(
        user_id=user_id,
        connected_tool_ids=connected_tool_ids or set(),
    )
    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
