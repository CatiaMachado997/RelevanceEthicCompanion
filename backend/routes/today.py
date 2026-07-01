"""Sprint F Task 6 — `/api/today/feed` route.

Single GET endpoint that aggregates a cross-source "what's happening today"
feed for the dashboard's Today surface. Pulls from existing tables only —
no new aggregation service. Read-only on user-owned data.

ESL note: matches the weekly_review precedent. This is a read-only aggregator
over the user's own data; no proactive user-facing action is produced, so the
route does not pass through `EthicalSafeguardLayer.evaluate_action`. Auth is
`get_current_read_user_id`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from utils.db import get_db_connection
from utils.supabase_auth import get_current_read_user_id

logger = logging.getLogger(__name__)

# NOTE: router does NOT carry a prefix — main.py sets the prefix when including.
router = APIRouter(tags=["today"])


def _serialize_task(row: dict) -> Dict[str, Any]:
    due = row.get("due_date")
    return {
        "id": str(row["id"]),
        "title": row.get("title") or "",
        "status": row.get("status"),
        "priority": row.get("priority"),
        "due_date": due.isoformat() if hasattr(due, "isoformat") and due else None,
        "project_id": str(row["project_id"]) if row.get("project_id") else None,
    }


def _serialize_source_item(row: dict) -> Dict[str, Any]:
    item_at = row.get("item_at") or row.get("synced_at")
    metadata = row.get("metadata") or {}
    if isinstance(metadata, str):
        import json as _json
        try:
            metadata = _json.loads(metadata)
        except Exception:
            metadata = {}
    body = row.get("body") or ""
    snippet = body.strip().splitlines()[0] if body else ""
    if len(snippet) > 200:
        snippet = snippet[:200].rstrip() + "..."
    # Best-effort URL: connectors typically stash a permalink under metadata.
    url = (
        metadata.get("url")
        or metadata.get("permalink")
        or metadata.get("link")
        or None
    )
    return {
        "id": str(row["id"]),
        "title": row.get("title") or "",
        "snippet": snippet,
        "timestamp": item_at.isoformat() if hasattr(item_at, "isoformat") and item_at else None,
        "source_ref": row.get("external_id"),
        "url": url,
    }


def _fetch_tasks_due_today(user_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, status, priority, due_date, project_id
                FROM tasks
                WHERE user_id = %s
                  AND status NOT IN ('done', 'cancelled')
                  AND due_date IS NOT NULL
                  AND due_date::date = (NOW() AT TIME ZONE 'UTC')::date
                ORDER BY priority ASC, due_date ASC
                LIMIT 10
                """,
                (user_id,),
            )
            return [_serialize_task(r) for r in (cur.fetchall() or [])]


def _fetch_tasks_overdue(user_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, status, priority, due_date, project_id
                FROM tasks
                WHERE user_id = %s
                  AND status NOT IN ('done', 'cancelled')
                  AND due_date IS NOT NULL
                  AND due_date < (NOW() AT TIME ZONE 'UTC')::date
                ORDER BY due_date ASC
                LIMIT 10
                """,
                (user_id,),
            )
            return [_serialize_task(r) for r in (cur.fetchall() or [])]


def _fetch_recent_source_items(user_id: str, source_type: str, limit: int = 5) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, body, metadata, item_at, synced_at, external_id
                FROM source_items
                WHERE user_id = %s
                  AND source_type = %s
                  AND embedding_status = 'indexed'
                  AND synced_at > NOW() - INTERVAL '24 hours'
                ORDER BY COALESCE(item_at, synced_at) DESC
                LIMIT %s
                """,
                (user_id, source_type, limit),
            )
            return [_serialize_source_item(r) for r in (cur.fetchall() or [])]


def _fetch_calendar_today(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch today's calendar events from source_items (source_type='google_calendar').

    Returns empty list when no calendar source is connected/indexed.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, body, metadata, item_at, synced_at, external_id
                FROM source_items
                WHERE user_id = %s
                  AND source_type = 'google_calendar'
                  AND item_at IS NOT NULL
                  AND item_at::date = (NOW() AT TIME ZONE 'UTC')::date
                ORDER BY item_at ASC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [_serialize_source_item(r) for r in (cur.fetchall() or [])]


@router.get("/feed", response_model=Dict[str, Any])
async def get_today_feed(
    user_id: str = Depends(get_current_read_user_id),
) -> Dict[str, Any]:
    """Return cross-source items for the dashboard Today surface.

    Each list is independent — empty arrays mean "nothing to show" so the
    frontend can render the per-widget empty state. Queries run in parallel
    via asyncio.to_thread since the underlying DB driver is sync.
    """
    try:
        (
            tasks_due_today,
            tasks_overdue,
            recent_emails,
            recent_slack,
            calendar_today,
        ) = await asyncio.gather(
            asyncio.to_thread(_fetch_tasks_due_today, user_id),
            asyncio.to_thread(_fetch_tasks_overdue, user_id),
            asyncio.to_thread(_fetch_recent_source_items, user_id, "gmail", 5),
            asyncio.to_thread(_fetch_recent_source_items, user_id, "slack", 5),
            asyncio.to_thread(_fetch_calendar_today, user_id, 10),
        )
    except Exception as e:
        logger.error(f"Failed to build today feed: {e}")
        raise HTTPException(status_code=500, detail="Failed to build today feed")

    return {
        "tasks_due_today": tasks_due_today,
        "tasks_overdue": tasks_overdue,
        "recent_emails": recent_emails,
        "recent_slack": recent_slack,
        "calendar_today": calendar_today,
    }
