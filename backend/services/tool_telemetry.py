"""Tool-call telemetry service — Sprint C Task 2.

Captures every tool invocation across chat turns and scheduled flows into
the ``tool_call_events`` table (migration 012). Append-only.

Sync, class-based, mirrors :class:`services.work_rollups.WorkRollupsService`.
JSONB columns are serialized via ``json.dumps`` to match the pattern used
elsewhere in the codebase (see ``services/data_ingestion.py``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


_INSERT_SQL = """
INSERT INTO tool_call_events
    (user_id, tool_name, source, source_ref, input, output,
     status, error_message, esl_decision, latency_ms,
     planner_run_id, step_index, action_index)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id;
"""


def _to_jsonb(value: Any) -> Optional[str]:
    """Coerce a Python value into a JSON string for a JSONB column.

    ``None`` stays ``None`` (so the column is NULL). Everything else is
    routed through ``json.dumps``; raw strings are wrapped as JSON strings,
    not inserted verbatim.
    """
    if value is None:
        return None
    return json.dumps(value)


class ToolTelemetryService:
    """Service for inserting and querying ``tool_call_events`` rows."""

    def record_tool_call(
        self,
        user_id: str,
        tool_name: str,
        source: str,
        source_ref: Optional[str],
        input: dict,
        output: Optional[Any],
        status: str,
        error_message: Optional[str] = None,
        esl_decision: Optional[str] = None,
        latency_ms: Optional[int] = None,
        # Sprint I — breadcrumbs back to the parent planner_runs row.
        # All three are optional and default to NULL so callers from
        # outside the orchestrator (e.g. scheduled flows) need no change.
        planner_run_id: Optional[str] = None,
        step_index: Optional[int] = None,
        action_index: Optional[int] = None,
    ) -> str:
        """Insert one ``tool_call_events`` row and return its UUID.

        Telemetry must never break the calling flow, so any DB error is
        swallowed and logged at WARNING level — the method then returns
        an empty string.
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        _INSERT_SQL,
                        (
                            user_id,
                            tool_name,
                            source,
                            source_ref,
                            _to_jsonb(input or {}),
                            _to_jsonb(output),
                            status,
                            error_message,
                            esl_decision,
                            latency_ms,
                            planner_run_id,
                            step_index,
                            action_index,
                        ),
                    )
                    row = cur.fetchone()
                conn.commit()
            if row is None:
                return ""
            # dict_row factory → {"id": UUID(...)}
            return str(row["id"])
        except Exception as exc:  # noqa: BLE001 — telemetry must not raise
            logger.warning(
                "tool_telemetry: failed to record tool call %s for user %s: %s",
                tool_name,
                user_id,
                exc,
            )
            return ""

    def list_tool_calls(
        self,
        user_id: str,
        *,
        tool_name: Optional[str] = None,
        source: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return recent ``tool_call_events`` rows for ``user_id``.

        Newest first. JSONB columns are decoded by psycopg's dict cursor.
        """
        clauses = ["user_id = %s"]
        params: List[Any] = [user_id]

        if tool_name is not None:
            clauses.append("tool_name = %s")
            params.append(tool_name)
        if source is not None:
            clauses.append("source = %s")
            params.append(source)
        if since is not None:
            clauses.append("created_at >= %s")
            params.append(since)

        where = " AND ".join(clauses)
        sql = (
            "SELECT id, user_id, tool_name, source, source_ref, input, output, "
            "status, error_message, esl_decision, latency_ms, created_at "
            f"FROM tool_call_events WHERE {where} "
            "ORDER BY created_at DESC LIMIT %s;"
        )
        params.append(limit)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
        return [dict(r) for r in rows]
