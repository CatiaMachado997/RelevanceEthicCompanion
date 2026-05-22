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
from config import settings as _settings

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
            return

        # Sprint K — schedule a fire-and-forget memory write if this run
        # is worth remembering. Eligibility:
        #   - status == 'completed'
        #   - at least one observation across all steps has status == 'ok'
        # We don't have user_id / message_text in this function's args, so
        # we fetch them via the run's conversation_turn_id FK.
        if not _settings.EPISODIC_MEMORY_ENABLED:
            return
        if status != "completed":
            return
        has_ok = any(
            (obs or {}).get("status") == "ok"
            for step in (plan_steps or [])
            for obs in (step.get("observations") or [])
        )
        if not has_ok:
            return
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT pr.user_id, ct.content AS message_text
                             FROM planner_runs pr
                        LEFT JOIN conversation_turns ct
                               ON ct.id = pr.conversation_turn_id
                            WHERE pr.id = %s""",
                        (run_id,),
                    )
                    row = cur.fetchone() or {}
            user_id = row.get("user_id")
            message_text = row.get("message_text") or ""
            if not user_id or not message_text:
                return  # nothing useful to embed; degrade silently
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "planner_run_memory: finalize lookup failed for %s: %s",
                run_id, exc,
            )
            return
        try:
            import asyncio
            from services.planner_run_memory import PlannerRunMemoryService

            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    PlannerRunMemoryService().write(
                        user_id=str(user_id),
                        planner_run_id=run_id,
                        message_text=message_text,
                        plan_steps=plan_steps,
                    )
                )
            # If no loop is running (e.g. tests calling finalize from a
            # sync context), skip — those tests won't exercise the memory
            # write path anyway.
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "planner_run_memory: schedule failed for %s: %s", run_id, exc
            )
