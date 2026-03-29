# backend/services/context_snapshot.py
"""
360° User Context Snapshot

Synchronously queries M1 (PostgreSQL) to build a summary of the user's
current work state. Used by the dashboard Today view and injected into
the chat system prompt.

No LLM calls. No Weaviate. Just fast SQL.
"""
from datetime import datetime, timedelta, timezone
from typing import Any
import logging

from utils.db import get_db_connection

logger = logging.getLogger(__name__)
UTC = timezone.utc


class ContextSnapshotService:
    """Compute a point-in-time 360° context snapshot from PostgreSQL."""

    def compute(self, user_id: str) -> dict[str, Any]:
        now = datetime.now(UTC)
        in_7_days = now + timedelta(days=7)
        in_24h = now + timedelta(hours=24)

        snapshot: dict[str, Any] = {
            "computed_at": now.isoformat(),
            "tasks_due_soon": [],
            "overdue_count": 0,
            "active_projects": [],
            "upcoming_events": [],
            "active_goals": [],
            "calendar_pressure": "light",
        }

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Tasks due within the next 7 days (not done/cancelled)
                cur.execute(
                    """
                    SELECT t.id, t.title, t.status, t.due_date, t.priority,
                           p.title AS project_title
                    FROM tasks t
                    LEFT JOIN projects p ON p.id = t.project_id
                    WHERE t.user_id = %s
                      AND t.status NOT IN ('done', 'cancelled')
                      AND t.due_date IS NOT NULL
                      AND t.due_date <= %s
                    ORDER BY t.due_date ASC, t.priority DESC
                    LIMIT 10
                    """,
                    (user_id, in_7_days),
                )
                snapshot["tasks_due_soon"] = [
                    {
                        "id": str(r["id"]),
                        "title": r["title"],
                        "status": r["status"],
                        "due_date": r["due_date"].isoformat() if r["due_date"] else None,
                        "priority": r["priority"],
                        "project_title": r["project_title"],
                    }
                    for r in cur.fetchall()
                ]

                # Count overdue tasks (past due, not done/cancelled)
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM tasks
                    WHERE user_id = %s
                      AND status NOT IN ('done', 'cancelled')
                      AND due_date IS NOT NULL
                      AND due_date < %s
                    """,
                    (user_id, now),
                )
                row = cur.fetchone()
                snapshot["overdue_count"] = row["cnt"] if row else 0

                # Active projects with open/done task counts
                cur.execute(
                    """
                    SELECT p.id, p.title,
                           COUNT(t.id) FILTER (
                               WHERE t.status NOT IN ('done', 'cancelled')
                           ) AS open_tasks,
                           COUNT(t.id) FILTER (
                               WHERE t.status = 'done'
                           ) AS done_tasks
                    FROM projects p
                    LEFT JOIN tasks t ON t.project_id = p.id
                    WHERE p.user_id = %s AND p.status = 'active'
                    GROUP BY p.id, p.title
                    ORDER BY p.updated_at DESC
                    LIMIT 5
                    """,
                    (user_id,),
                )
                snapshot["active_projects"] = [
                    {
                        "id": str(r["id"]),
                        "title": r["title"],
                        "open_tasks": r["open_tasks"],
                        "done_tasks": r["done_tasks"],
                    }
                    for r in cur.fetchall()
                ]

                # Upcoming events in the next 24h (from the 'events' table)
                cur.execute(
                    """
                    SELECT title, start_time, location
                    FROM events
                    WHERE user_id = %s
                      AND start_time >= %s
                      AND start_time <= %s
                    ORDER BY start_time ASC
                    LIMIT 5
                    """,
                    (user_id, now, in_24h),
                )
                events = cur.fetchall()
                snapshot["upcoming_events"] = [
                    {
                        "title": r["title"],
                        "start_time": r["start_time"].isoformat() if r["start_time"] else None,
                        "location": r["location"],
                    }
                    for r in events
                ]
                event_count = len(events)
                snapshot["calendar_pressure"] = (
                    "heavy" if event_count >= 4
                    else "moderate" if event_count >= 2
                    else "light"
                )

                # Top active goals
                cur.execute(
                    """
                    SELECT id, title, priority, target_date
                    FROM goals
                    WHERE user_id = %s AND status = 'active'
                    ORDER BY priority ASC
                    LIMIT 5
                    """,
                    (user_id,),
                )
                snapshot["active_goals"] = [
                    {
                        "id": str(r["id"]),
                        "title": r["title"],
                        "priority": r["priority"],
                        "target_date": (
                            r["target_date"].isoformat() if r["target_date"] else None
                        ),
                    }
                    for r in cur.fetchall()
                ]

        return snapshot
