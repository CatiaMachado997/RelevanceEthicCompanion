"""
Dashboard aggregated-overview route.

Returns a single JSON with all counts needed to render the dashboard's
tools launcher. Replaces the 7 parallel fetches that the old frontend
made, each of which had its own round-trip + auth overhead.
"""

from fastapi import APIRouter, Depends
from utils.supabase_auth import get_current_read_user_id
from utils.db import get_db_connection

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/overview")
async def overview(
    user_id: str = Depends(get_current_read_user_id),
) -> dict:
    """Return every count the dashboard launcher needs, in one response."""
    queries = [
        (
            "goals_active",
            "SELECT COUNT(*) AS cnt FROM goals WHERE user_id = %s AND status = 'active'",
        ),
        (
            "tasks_open",
            "SELECT COUNT(*) AS cnt FROM tasks WHERE user_id = %s AND status IN ('todo','in_progress')",
        ),
        (
            "projects_active",
            "SELECT COUNT(*) AS cnt FROM projects WHERE user_id = %s AND status = 'active'",
        ),
        (
            "values_count",
            "SELECT COUNT(*) AS cnt FROM user_values WHERE user_id = %s AND active = TRUE",
        ),
        ("documents_count", "SELECT COUNT(*) AS cnt FROM documents WHERE user_id = %s"),
        (
            "esl_decisions_7d",
            "SELECT COUNT(*) AS cnt FROM esl_audit_log WHERE user_id = %s AND created_at > NOW() - INTERVAL '7 days'",
        ),
        (
            "notifications_unread",
            "SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = %s AND read = FALSE",
        ),
    ]

    out: dict = {}
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for key, sql in queries:
                cur.execute(sql, (user_id,))
                row = cur.fetchone()
                out[key] = (row or {}).get("cnt", 0)
    return out
