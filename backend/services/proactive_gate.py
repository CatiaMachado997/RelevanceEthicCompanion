"""Proactive notification ESL gate.

Per CLAUDE.md, every user-facing action MUST pass through the Ethical Safeguard
Layer. Scheduler flows that emit proactive notifications (morning brief,
pre-meeting brief, deadline warning, weekly digest, etc.) call this helper to
ensure their output is evaluated before being persisted/dispatched.

Fail-closed: any exception or VETO results in (False, original_content) so a
broken ESL never silently lets unevaluated content reach the user.
"""

import logging
from typing import Optional

from esl.models import (
    ProposedAction,
    ActionType,
    ESLDecisionStatus,
    UrgencyLevel,
)
from orchestrator.nodes.esl import get_esl

logger = logging.getLogger(__name__)


async def gate_proactive_notification(
    user_id: str,
    notification_type: str,
    content: str,
    urgency: str = "low",
    metadata: Optional[dict] = None,
) -> tuple[bool, str]:
    """Run a proactive notification through ESL.

    Args:
        user_id: User the notification targets.
        notification_type: ProposedAction.content_type — e.g.
            'daily_focus_plan', 'pre_meeting_brief', 'deadline_warning'.
        content: The notification body the LLM produced.
        urgency: 'low' | 'medium' | 'high' (mapped to UrgencyLevel).
        metadata: Optional extra context forwarded to ESL.

    Returns:
        (should_send, final_content):
          - APPROVED → (True, content)
          - MODIFIED → (True, modified_content)
          - VETOED   → (False, content)
          - exception → (False, content)  # fail-closed
    """
    try:
        try:
            urgency_level = UrgencyLevel(urgency)
        except ValueError:
            urgency_level = UrgencyLevel.LOW

        proposed = ProposedAction(
            action_type=ActionType.PUSH_NOTIFICATION,
            content_type=notification_type,
            content=content,
            urgency=urgency_level,
            metadata=metadata or {},
        )

        esl = get_esl()
        decision = await esl.evaluate_action(proposed, user_id)

        if decision.status == ESLDecisionStatus.APPROVED:
            return (True, content)
        if decision.status == ESLDecisionStatus.MODIFIED:
            modified_content = content
            if decision.modified_action and decision.modified_action.content:
                modified_content = decision.modified_action.content
            return (True, modified_content)
        # VETOED
        logger.info(
            "[proactive_gate] ESL vetoed notification user=%s type=%s reason=%s",
            user_id,
            notification_type,
            decision.reason,
        )
        return (False, content)
    except Exception as e:
        logger.warning(
            "[proactive_gate] ESL evaluation failed (fail-closed) "
            "user=%s type=%s error=%s",
            user_id,
            notification_type,
            e,
            exc_info=True,
        )
        return (False, content)
