"""
ESL Tool Gate — pre-execution trust check for marketplace write actions.

Rules:
  risk=low, no record  → APPROVED (auto-approve)
  risk=low|medium, record=allow → APPROVED
  risk=high, any record → PENDING_CONFIRMATION (always confirm)
  record=ask or no record (medium) → PENDING_CONFIRMATION
  record=deny → VETOED
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


class GateResult(str, Enum):
    APPROVED = "APPROVED"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    VETOED = "VETOED"


@dataclass
class GateDecision:
    status: GateResult
    preview: str = ""
    reason: str = ""


class ESLToolGate:
    """Check tool_permissions before executing a write action."""

    async def check(
        self,
        user_id: str,
        tool_id: str,
        action_name: str,
        risk_level: str,
        preview: str,
    ) -> GateDecision:
        """
        Returns a GateDecision. Never raises — returns PENDING_CONFIRMATION
        on any unexpected error so the user always stays in the loop.
        """
        try:
            trust = await self._get_trust(user_id, tool_id, action_name)

            # High-risk: always confirm regardless of stored trust
            if risk_level == "high":
                return GateDecision(
                    status=GateResult.PENDING_CONFIRMATION,
                    preview=preview,
                    reason="High-risk action always requires confirmation.",
                )

            # Explicit deny
            if trust == "deny":
                return GateDecision(
                    status=GateResult.VETOED,
                    reason=f"User has denied {tool_id}/{action_name}.",
                )

            # Low risk with no record or allow → auto-approve
            if risk_level == "low" and trust in ("allow", None):
                return GateDecision(status=GateResult.APPROVED)

            # Explicit allow (medium risk)
            if trust == "allow":
                return GateDecision(status=GateResult.APPROVED)

            # Default: ask (no record for medium, or record=ask)
            return GateDecision(
                status=GateResult.PENDING_CONFIRMATION,
                preview=preview,
                reason="First-time action — confirmation required.",
            )

        except Exception as e:
            logger.error(f"ESLToolGate.check error: {e}")
            return GateDecision(
                status=GateResult.PENDING_CONFIRMATION,
                preview=preview,
                reason="Gate check failed — defaulting to confirmation.",
            )

    async def _get_trust(
        self, user_id: str, tool_id: str, action_name: str
    ) -> str | None:
        """Return trust_level string or None if no record exists."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT trust_level FROM tool_permissions
                    WHERE user_id = %s AND tool_id = %s AND action_name = %s
                      AND (expires_at IS NULL OR expires_at > now())
                    """,
                    (user_id, tool_id, action_name),
                )
                row = cur.fetchone()
        return row["trust_level"] if row else None

    async def set_trust(
        self,
        user_id: str,
        tool_id: str,
        action_name: str,
        trust_level: str,
    ) -> None:
        """Upsert trust_level for a user/tool/action triple."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tool_permissions (user_id, tool_id, action_name, trust_level)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, tool_id, action_name)
                    DO UPDATE SET trust_level = EXCLUDED.trust_level, granted_at = now()
                    """,
                    (user_id, tool_id, action_name, trust_level),
                )
