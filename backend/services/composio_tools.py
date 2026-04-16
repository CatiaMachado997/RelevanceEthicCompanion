"""
Composio tool integration — loads per-user tools from Composio's managed platform.

Composio handles OAuth, token storage, and token refresh for all connected apps.
We tag each returned LangChain StructuredTool (a BaseTool subclass) with ESL metadata
(tool_id, action_name, risk_level) so ESLToolGate in orchestrator/nodes/tools.py
can gate them without any changes.

Usage:
    from services.composio_tools import get_composio_tools_for_user

    tools = await get_composio_tools_for_user(
        user_id="uuid",
        connected_tool_ids={"github", "notion"},
    )
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from langchain_core.tools import BaseTool

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maps our internal tool_id (in tool_definitions table) → Composio toolkit slug
TOOL_ID_TO_COMPOSIO_TOOLKIT: dict[str, str] = {
    "github": "github",
    "notion": "notion",
    "slack": "slack",
    "gmail_write": "gmail",
    "google_calendar_write": "googlecalendar",
}

# Maps Composio action slug → (our_tool_id, our_action_name, risk_level)
_ACTION_METADATA: dict[str, tuple[str, str, str]] = {
    "GITHUB_LIST_REPOSITORY_ISSUES": ("github", "list_issues", "low"),
    "GITHUB_CREATE_AN_ISSUE": ("github", "create_issue", "medium"),
    "GITHUB_CREATE_AN_ISSUE_COMMENT": ("github", "add_comment", "medium"),
    "NOTION_SEARCH": ("notion", "search_pages", "low"),
    "NOTION_CREATE_PAGE": ("notion", "create_page", "medium"),
    "GMAIL_CREATE_EMAIL_DRAFT": ("gmail_write", "create_draft", "low"),
    "GMAIL_REPLY_TO_THREAD": ("gmail_write", "send_reply", "high"),
    "GOOGLECALENDAR_CREATE_EVENT": ("google_calendar_write", "create_event", "low"),
    "GOOGLECALENDAR_UPDATE_EVENT": ("google_calendar_write", "update_event", "medium"),
    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL": ("slack", "send_message", "high"),
    "SLACK_FETCH_CONVERSATION_HISTORY": ("slack", "read_channel", "low"),
}

# Which Composio action slugs belong to each toolkit slug
_TOOLKIT_ACTIONS: dict[str, list[str]] = {
    "github": [
        "GITHUB_LIST_REPOSITORY_ISSUES",
        "GITHUB_CREATE_AN_ISSUE",
        "GITHUB_CREATE_AN_ISSUE_COMMENT",
    ],
    "notion": [
        "NOTION_SEARCH",
        "NOTION_CREATE_PAGE",
    ],
    "gmail": [
        "GMAIL_CREATE_EMAIL_DRAFT",
        "GMAIL_REPLY_TO_THREAD",
    ],
    "googlecalendar": [
        "GOOGLECALENDAR_CREATE_EVENT",
        "GOOGLECALENDAR_UPDATE_EVENT",
    ],
    "slack": [
        "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL",
        "SLACK_FETCH_CONVERSATION_HISTORY",
    ],
}

# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_composio_client: Any = None
_composio_lock = threading.Lock()


def _get_composio_client() -> Any:
    """Lazy singleton — created once per process when COMPOSIO_API_KEY is set."""
    global _composio_client
    if _composio_client is None:
        with _composio_lock:
            if _composio_client is None:  # double-checked locking
                from composio import Composio
                from composio_langchain import LangchainProvider

                _composio_client = Composio(
                    provider=LangchainProvider(),
                    api_key=settings.COMPOSIO_API_KEY,
                )
    return _composio_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_composio_tools_for_user(
    user_id: str,
    connected_tool_ids: set[str],
) -> list[BaseTool]:
    """Return ESL-tagged LangChain tools for the user's connected apps.

    Args:
        user_id: Internal user UUID — used as Composio entity_id for token isolation.
        connected_tool_ids: Tool IDs from user_tool_connections table (our source of truth).

    Returns:
        List of BaseTool with .metadata["tool_id"], ["action_name"], ["risk_level"] set.
        Returns [] on error — never raises.
    """
    # 1. Nothing connected → nothing to load.
    if not connected_tool_ids:
        return []

    # 2. Guard: no API key configured.
    if not settings.COMPOSIO_API_KEY:
        logger.warning("COMPOSIO_API_KEY is not set — skipping Composio tool loading.")
        return []

    try:
        # 3. Map our tool IDs → Composio toolkit slugs (skip unknown IDs).
        toolkit_slugs: list[str] = []
        for tool_id in connected_tool_ids:
            slug = TOOL_ID_TO_COMPOSIO_TOOLKIT.get(tool_id)
            if slug:
                toolkit_slugs.append(slug)
            else:
                logger.debug(
                    "No Composio toolkit mapping for tool_id=%r — skipping.", tool_id
                )

        if not toolkit_slugs:
            return []

        # 4. Build per-toolkit action filter.
        tools_filter: dict[str, list[str]] = {
            slug: _TOOLKIT_ACTIONS[slug]
            for slug in toolkit_slugs
            if slug in _TOOLKIT_ACTIONS
        }

        # 5. Create a per-user Composio session (synchronous → offload to thread).
        client = _get_composio_client()
        session = await asyncio.to_thread(
            client.create,
            user_id=user_id,
            toolkits=toolkit_slugs,
            tools=tools_filter,
            manage_connections=False,
        )

        # 6. Retrieve the LangChain StructuredTool list (also synchronous).
        raw_tools: list[Any] = await asyncio.to_thread(
            session.tools
        )  # session.tools() called in thread
        if not raw_tools:
            logger.debug(
                "Composio: session.tools() returned empty for user %s", user_id
            )
            return []

        # 7 & 8. Tag each tool with ESL metadata.
        tagged: list[BaseTool] = []
        for tool in raw_tools:
            # Try exact name, then upper-cased variant.
            meta = _ACTION_METADATA.get(tool.name) or _ACTION_METADATA.get(
                tool.name.upper()
            )

            existing: dict = getattr(tool, "metadata", None) or {}

            if meta:
                tool_id_val, action_name_val, risk_level_val = meta
            else:
                # 9. Fallback for unknown action slugs.
                logger.warning(
                    "No _ACTION_METADATA entry for action %r — using fallback.",
                    tool.name,
                )
                tool_id_val = "composio"
                action_name_val = tool.name
                risk_level_val = "medium"

            tool.metadata = {
                **existing,
                "tool_id": tool_id_val,
                "action_name": action_name_val,
                "risk_level": risk_level_val,
            }
            tagged.append(tool)

        # 10. Return tagged tools.
        logger.debug(
            "Composio: loaded %d tagged tool(s) for user %s.", len(tagged), user_id
        )
        return tagged

    except Exception as exc:
        logger.warning(
            "get_composio_tools_for_user failed for user %s: %s", user_id, exc
        )
        return []
