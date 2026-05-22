"""Sprint I Task 6: planner_runs lifecycle writes.

PlannerRunsService manages the parent row in `planner_runs` per agent
turn. The row is INSERTed on first planner invocation (status='running')
and UPDATEd at the end of the turn with the resolved status, totals,
and full plan_steps blob.

Like other telemetry in this codebase (services/tool_telemetry.py), all
DB failures are logged at WARNING level and swallowed — telemetry must
never break the calling flow.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


_VALID_STATUSES = frozenset(
    {"running", "completed", "cap_hit", "error", "vetoed"}
)


class PlannerRunsService:
    """Service for inserting and finalizing `planner_runs` rows."""

    def create(
        self,
        user_id: str,
        conversation_id: Optional[str],
        intent: Optional[str],
    ) -> str:
        """Insert a new planner_runs row with status='running'.

        Returns the row's UUID as a string, or empty string on failure.
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO planner_runs
                            (user_id, conversation_id, intent, status)
                        VALUES (%s, %s, %s, 'running')
                        RETURNING id
                        """,
                        (user_id, conversation_id, intent),
                    )
                    row = cur.fetchone()
                conn.commit()
            if row is None:
                return ""
            return str(row["id"])
        except Exception as exc:  # noqa: BLE001 — telemetry must not raise
            logger.warning(
                "planner_runs: create failed for user %s: %s", user_id, exc
            )
            return ""

    def finalize(
        self,
        run_id: str,
        status: str,
        total_steps: int,
        total_actions: int,
        total_duration_ms: int,
        plan_steps: List[dict],
    ) -> None:
        """UPDATE the planner_runs row with final state.

        `status` must be one of the CHECK-allowed values; an invalid
        value is logged and the write is skipped (so we never produce
        a constraint violation in production).
        """
        if status not in _VALID_STATUSES:
            logger.warning(
                "planner_runs: refusing to finalize with invalid status %r", status
            )
            return
        if not run_id:
            return  # create() failed earlier — nothing to update
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE planner_runs
                           SET status = %s,
                               total_steps = %s,
                               total_actions = %s,
                               total_duration_ms = %s,
                               plan_steps = %s::jsonb,
                               finished_at = NOW()
                         WHERE id = %s
                        """,
                        (
                            status,
                            total_steps,
                            total_actions,
                            total_duration_ms,
                            json.dumps(plan_steps or []),
                            run_id,
                        ),
                    )
                conn.commit()
        except Exception as exc:  # noqa: BLE001 — telemetry must not raise
            logger.warning(
                "planner_runs: finalize failed for run %s: %s", run_id, exc
            )
