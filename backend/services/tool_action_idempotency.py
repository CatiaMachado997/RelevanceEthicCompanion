"""Durable exactly-once guard for side-effecting agent tool actions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

from utils.db import get_db_connection


@dataclass(frozen=True)
class ActionClaim:
    claimed: bool
    status: str
    output: Any = None
    error_message: Optional[str] = None


def build_action_key(
    *,
    user_id: str,
    conversation_id: Optional[str],
    planner_run_id: Optional[str],
    step_index: int,
    action_index: int,
    tool_name: str,
    tool_input: dict,
    request_id: Optional[str] = None,
) -> str:
    """Return a stable key for one planned action, independent of retries."""
    payload = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "tool_name": tool_name,
        "input": tool_input,
    }
    if request_id:
        # An explicit UI retry may produce a new planner run or action order.
        # Keep the write identity stable across that replan.
        payload["request_id"] = request_id
    else:
        payload.update(
            {
                "planner_run_id": planner_run_id,
                "step_index": step_index,
                "action_index": action_index,
            }
        )
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ToolActionIdempotencyService:
    """Claim and resolve write actions using an atomic PostgreSQL ledger."""

    def claim(
        self,
        *,
        action_key: str,
        user_id: str,
        conversation_id: Optional[str],
        planner_run_id: Optional[str],
        step_index: int,
        action_index: int,
        tool_name: str,
        tool_input: dict,
    ) -> ActionClaim:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tool_action_executions
                        (action_key, user_id, conversation_id, planner_run_id,
                         step_index, action_index, tool_name, input)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (action_key) DO NOTHING
                    RETURNING status
                    """,
                    (
                        action_key,
                        user_id,
                        conversation_id,
                        planner_run_id,
                        step_index,
                        action_index,
                        tool_name,
                        json.dumps(tool_input or {}, default=str),
                    ),
                )
                inserted = cur.fetchone()
                if inserted:
                    conn.commit()
                    return ActionClaim(claimed=True, status="started")
                cur.execute(
                    """
                    SELECT status, output, error_message
                    FROM tool_action_executions
                    WHERE action_key = %s AND user_id = %s
                    """,
                    (action_key, user_id),
                )
                row = cur.fetchone()
        if not row:
            return ActionClaim(claimed=False, status="unknown")
        return ActionClaim(
            claimed=False,
            status=str(row["status"]),
            output=row.get("output"),
            error_message=row.get("error_message"),
        )

    def finish(
        self,
        *,
        action_key: str,
        user_id: str,
        status: str,
        output: Any = None,
        error_message: Optional[str] = None,
    ) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tool_action_executions
                    SET status = %s, output = %s::jsonb, error_message = %s,
                        completed_at = NOW(), updated_at = NOW()
                    WHERE action_key = %s AND user_id = %s
                    """,
                    (
                        status,
                        json.dumps(output, default=str) if output is not None else None,
                        error_message,
                        action_key,
                        user_id,
                    ),
                )
            conn.commit()
