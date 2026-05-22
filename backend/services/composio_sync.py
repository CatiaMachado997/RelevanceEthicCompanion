"""Composio Sync Service.

Fetches recent data from connected integrations via Composio and upserts
the results into the M2 vector store (source_items table) for ESL context.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from config import settings
from utils.db import get_db_connection

logger = logging.getLogger(__name__)

# Mapping from our tool_id to the Composio action and result parser
_TOOL_CONFIG: dict[str, dict[str, Any]] = {
    "gmail": {
        "action": "GMAIL_FETCH_EMAILS",
        "params": {"max_results": 20},
        "source_type": "gmail",
    },
    "gmail_write": {
        "action": "GMAIL_FETCH_EMAILS",
        "params": {"max_results": 20},
        "source_type": "gmail",
    },
    "google_calendar": {
        "action": "GOOGLECALENDAR_LIST_EVENTS",
        "params": {"max_results": 20},
        "source_type": "google_calendar",
    },
    "google_calendar_write": {
        "action": "GOOGLECALENDAR_LIST_EVENTS",
        "params": {"max_results": 20},
        "source_type": "google_calendar",
    },
    "slack": {
        "action": "SLACK_FETCH_CONVERSATION_HISTORY",
        "params": {"limit": 20},
        "source_type": "slack",
    },
    "github": {
        "action": "GITHUB_LIST_REPOSITORY_ISSUES",
        "params": {"state": "open", "per_page": 20},
        "source_type": "github",
    },
    "notion": {
        "action": "NOTION_SEARCH",
        "params": {"query": "", "page_size": 20},
        "source_type": "notion",
    },
}


def _parse_items(tool_id: str, result: Any) -> list[dict[str, Any]]:
    """Extract normalised items from a Composio action result.

    Returns a list of dicts with keys: source_item_type, title, content, item_at.
    Never raises — returns [] on unexpected shapes.
    """
    items: list[dict[str, Any]] = []

    try:
        # Composio returns either a dict or an object with a data attribute
        data = result if isinstance(result, dict) else getattr(result, "data", {})

        source_type = _TOOL_CONFIG.get(tool_id, {}).get("source_type", tool_id)

        if source_type == "gmail":
            emails = data.get("emails") or data.get("messages") or []
            for email in emails:
                subject = email.get("subject") or "(no subject)"
                body = email.get("body") or email.get("snippet") or ""
                date_str = email.get("date") or email.get("internalDate") or None
                items.append(
                    {
                        "source_item_type": "email",
                        "title": subject,
                        "content": body[:4000],  # cap at 4 KB
                        "item_at": _parse_date(date_str),
                    }
                )

        elif source_type == "google_calendar":
            events = data.get("events") or data.get("items") or []
            for event in events:
                title = event.get("summary") or "(no title)"
                description = event.get("description") or ""
                start = (
                    (event.get("start") or {}).get("dateTime")
                    or (event.get("start") or {}).get("date")
                    or None
                )
                items.append(
                    {
                        "source_item_type": "calendar_event",
                        "title": title,
                        "content": description[:4000],
                        "item_at": _parse_date(start),
                    }
                )

        elif source_type == "slack":
            messages = data.get("messages") or []
            channel = data.get("channel") or "unknown"
            for msg in messages:
                text = msg.get("text") or ""
                ts = msg.get("ts") or None
                item_at = None
                if ts:
                    try:
                        item_at = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                    except (ValueError, TypeError):
                        item_at = None
                items.append(
                    {
                        "source_item_type": "slack_message",
                        "title": f"#{channel}",
                        "content": text[:4000],
                        "item_at": item_at,
                    }
                )

        elif source_type == "github":
            issues = data.get("issues") or data if isinstance(data, list) else []
            for issue in issues:
                title = issue.get("title") or "(no title)"
                body = issue.get("body") or ""
                repo = (issue.get("repository_url") or "").split("/")[-1]
                created = issue.get("created_at") or None
                label = f"[{repo}] {title}" if repo else title
                items.append(
                    {
                        "source_item_type": "github_issue",
                        "title": label,
                        "content": body[:4000],
                        "item_at": _parse_date(created),
                    }
                )

        elif source_type == "notion":
            results = data.get("results") or []
            for page in results:
                # Notion page title is nested in properties
                props = page.get("properties") or {}
                title_prop = (
                    props.get("title") or props.get("Name") or props.get("name") or {}
                )
                title_arr = (title_prop.get("title") or []) if isinstance(title_prop, dict) else []
                title = "".join(
                    t.get("plain_text", "") for t in title_arr if isinstance(t, dict)
                ) or page.get("url") or "(untitled)"
                edited = page.get("last_edited_time") or page.get("created_time") or None
                items.append(
                    {
                        "source_item_type": "notion_page",
                        "title": title,
                        "content": title,  # full content requires a separate blocks fetch
                        "item_at": _parse_date(edited),
                    }
                )

    except Exception as exc:
        logger.warning(f"[composio_sync] _parse_items failed for {tool_id}: {exc}")

    return items


def _parse_date(value: Any) -> datetime | None:
    """Try to parse various date string formats into a UTC datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        # ISO 8601 with or without trailing Z
        s = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        pass
    # Gmail internalDate is epoch milliseconds as a string
    try:
        return datetime.fromtimestamp(int(str(value)) / 1000, tz=timezone.utc)
    except (ValueError, TypeError):
        return None


def _execute_composio_action(user_id: str, action: str, params: dict) -> Any:
    """Blocking Composio action execution — run in a thread via asyncio.to_thread."""
    from composio_langchain import ComposioToolSet  # type: ignore[import]

    toolset = ComposioToolSet(
        api_key=settings.COMPOSIO_API_KEY,
        entity_id=user_id,
    )
    return toolset.execute_action(action=action, params=params)


def _upsert_items(user_id: str, source_type: str, items: list[dict[str, Any]]) -> int:
    """Insert/update items into source_items. Returns count of rows upserted."""
    if not items:
        return 0

    count = 0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for item in items:
                item_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO source_items
                        (id, user_id, source_type, source_item_type, title, content, item_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        item_id,
                        user_id,
                        source_type,
                        item.get("source_item_type", "unknown"),
                        item.get("title", ""),
                        item.get("content", ""),
                        item.get("item_at"),
                    ),
                )
                if cur.rowcount:
                    count += 1
    return count


async def sync_tool_data(user_id: str, tool_id: str) -> int:
    """Fetch recent data from a connected integration and store it in source_items.

    Args:
        user_id: The authenticated user's UUID.
        tool_id: One of the catalogue tool IDs (e.g. "gmail_write", "slack").

    Returns:
        Number of new items upserted. Returns 0 on any error — never raises.
    """
    if not settings.COMPOSIO_API_KEY:
        logger.warning("[composio_sync] COMPOSIO_API_KEY not set — skipping sync")
        return 0

    config = _TOOL_CONFIG.get(tool_id)
    if not config:
        logger.warning(f"[composio_sync] Unknown tool_id '{tool_id}' — skipping sync")
        return 0

    action = config["action"]
    params = config["params"]
    source_type = config["source_type"]

    try:
        result = await asyncio.to_thread(
            _execute_composio_action, user_id, action, params
        )
    except Exception as exc:
        logger.error(
            f"[composio_sync] Composio action {action} failed for user {user_id}: {exc}",
            exc_info=True,
        )
        return 0

    items = _parse_items(tool_id, result)
    if not items:
        logger.info(
            f"[composio_sync] No items returned for {tool_id} / user {user_id}"
        )
        return 0

    try:
        count = await asyncio.to_thread(_upsert_items, user_id, source_type, items)
        logger.info(
            f"[composio_sync] Upserted {count} items for {tool_id} / user {user_id}"
        )
        return count
    except Exception as exc:
        logger.error(
            f"[composio_sync] DB upsert failed for {tool_id} / user {user_id}: {exc}",
            exc_info=True,
        )
        return 0
