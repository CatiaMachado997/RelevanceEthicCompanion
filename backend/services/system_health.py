"""System health service — Sprint E Task 2.

Aggregates the data we already collect (``tool_call_events``,
``esl_audit_log``, in-memory APScheduler state) into the shape the
Transparency "System health" tab needs (Task 3 will build the route + UI).

Sync, class-based, mirrors :class:`services.work_rollups.WorkRollupsService`.
No new persistence — every read goes against the views from migration 014
or the live scheduler instance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


_TOOL_HEALTH_SQL = """
SELECT tool_name, source, calls_24h, success_rate,
       p50_latency_ms, p95_latency_ms
FROM v_tool_call_health
WHERE user_id = %s
ORDER BY calls_24h DESC, tool_name ASC;
"""

_ESL_SUMMARY_SQL = """
SELECT decision_status, count_24h, count_7d
FROM v_esl_decision_summary
WHERE user_id = %s;
"""


class SystemHealthService:
    """Read-only aggregations for the Transparency system-health surface."""

    def get_tool_health(self, user_id: str) -> List[Dict[str, Any]]:
        """Per-tool latency + success rate over the last 24h.

        Rows from ``v_tool_call_health`` for ``user_id``, sorted by
        ``calls_24h`` descending. Each row:
        ``{tool_name, source, calls_24h, success_rate, p50_latency_ms,
        p95_latency_ms}``.
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_TOOL_HEALTH_SQL, (user_id,))
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_esl_summary(self, user_id: str) -> Dict[str, Dict[str, int]]:
        """ESL decision counts rolled up from ``v_esl_decision_summary``.

        Returns ``{decision_status: {"count_24h": int, "count_7d": int}}``.
        Statuses with no rows simply don't appear.
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_ESL_SUMMARY_SQL, (user_id,))
                rows = cur.fetchall()

        out: Dict[str, Dict[str, int]] = {}
        for row in rows:
            status = row["decision_status"]
            out[status] = {
                "count_24h": int(row["count_24h"] or 0),
                "count_7d": int(row["count_7d"] or 0),
            }
        return out

    def get_scheduler_status(self) -> List[Dict[str, Any]]:
        """In-memory APScheduler job state — no DB.

        Returns ``[{job_id, next_run_time (ISO), trigger (str)}, ...]``.
        Returns ``[]`` if the scheduler isn't running yet (e.g. during
        unit tests, or before lifespan startup completes).
        """
        try:
            from services.scheduler import get_scheduler_instance

            inst = get_scheduler_instance()
            if inst is None or not getattr(inst, "_running", False):
                return []

            jobs = inst.scheduler.get_jobs()
            out: List[Dict[str, Any]] = []
            for job in jobs:
                out.append(
                    {
                        "job_id": job.id,
                        "next_run_time": (
                            job.next_run_time.isoformat()
                            if job.next_run_time
                            else None
                        ),
                        "trigger": str(job.trigger),
                    }
                )
            return out
        except Exception as e:
            logger.warning("get_scheduler_status failed: %s", e)
            return []
