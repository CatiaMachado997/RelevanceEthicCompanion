"""
Ethical Safeguard Layer - Core Engine

The heart of Ethic Companion's ethical decision-making system.

This class is the MANDATORY GATEWAY for all user-facing actions.
No action can bypass this evaluation.
"""

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.relevance import ContentSafetyCheck  # noqa: F401  (forward ref only)

from .models import (
    ProposedAction,
    ESLDecision,
    ESLDecisionStatus,
)
from .rules import (
    TimeBasedRules,
    ManipulationDetector,
    EngagementDetector,
    TopicFilter,
    semantic_manipulation_check,
)
from .audit import ESLAuditLogger

logger = logging.getLogger(__name__)


class EthicalSafeguardLayer:
    """
    The Ethical Safeguard Layer - Core Decision Engine

    Usage:
        esl = EthicalSafeguardLayer(context_manager, audit_logger)
        decision = await esl.evaluate_action(proposed_action, user_id)

        if decision.status == ESLDecisionStatus.APPROVED:
            # Proceed with action
            pass
        elif decision.status == ESLDecisionStatus.MODIFIED:
            # Use decision.modified_action instead
            pass
        # If VETOED, do nothing - this is correct behavior
    """

    def __init__(
        self,
        context_manager,
        audit_logger: Optional[ESLAuditLogger] = None,
        db_connection_factory=None,
        llm=None,
    ):
        """
        Initialize the ESL

        Args:
            context_manager: ContextManager instance for retrieving user context
            audit_logger: ESLAuditLogger instance for logging decisions
            db_connection_factory: Optional callable for database connections (enables audit persistence)
            llm: Optional LangChain LLM for semantic manipulation detection (E.2)
        """
        self.context_manager = context_manager
        self.llm = llm
        # Use provided audit_logger, or create one with optional database persistence
        self.audit_logger = audit_logger or ESLAuditLogger(
            db_connection_factory=db_connection_factory
        )

        # Initialize rule checkers
        self.time_rules = TimeBasedRules()
        self.manipulation_detector = ManipulationDetector()
        self.engagement_detector = EngagementDetector()
        self.topic_filter = TopicFilter()

    async def evaluate_action(
        self, proposed_action: ProposedAction, user_id: str
    ) -> ESLDecision:
        """
        Evaluate a proposed action against ethical safeguards

        This is the core method that MUST be called before any user-facing action.

        Args:
            proposed_action: The action the Orchestrator wants to take
            user_id: ID of the user affected by the action

        Returns:
            ESLDecision with status APPROVED, VETOED, or MODIFIED
        """
        # Step 1: Retrieve user context
        context = await self.context_manager.get_user_context(user_id)

        # Step 2: Run all ethical checks
        violated_values = []
        applied_rules = []
        reasons = []

        # Check 1: Time-based boundaries
        time_check = self.time_rules.check_boundaries(
            proposed_action, context.user_values, context.current_time
        )
        if not time_check.passed:
            violated_values.extend(time_check.violated_values)
            applied_rules.append("TimeBasedRules")
            reasons.append(time_check.reason)

        # Check 2: Manipulation detection
        manipulation_check = self.manipulation_detector.check_content(
            proposed_action.content or ""
        )
        if not manipulation_check.passed:
            applied_rules.append("ManipulationDetector")
            reasons.append(manipulation_check.reason)

        # Check 2b: Semantic manipulation detection (E.2 — LLM-based, only when llm available)
        content_text = proposed_action.content or ""
        if self.llm and len(content_text) > 100 and manipulation_check.passed:
            try:
                is_semantic_manipulation = await semantic_manipulation_check(
                    content_text, self.llm
                )
                if is_semantic_manipulation and manipulation_check.passed:
                    applied_rules.append("SemanticManipulationDetector")
                    reasons.append("LLM detected manipulative framing in content")
                    manipulation_check = manipulation_check.model_copy(
                        update={
                            "passed": False,
                            "reason": "Semantic manipulation detected",
                        }
                    )
            except Exception as e:
                logger.debug(f"Semantic manipulation check skipped: {e}")

        # Check 3: Engagement vs. Assistance intent
        engagement_check = self.engagement_detector.check_intent(proposed_action)
        if not engagement_check.passed:
            applied_rules.append("EngagementDetector")
            reasons.append(engagement_check.reason)

        # Check 4: Topic filter violations
        topic_check = self.topic_filter.check_topic(
            proposed_action, context.user_values
        )
        if not topic_check.passed:
            violated_values.extend(topic_check.violated_values)
            applied_rules.append("TopicFilter")
            reasons.append(topic_check.reason)

        # Check 5: Focus mode respect
        focus_mode_violated = (
            context.focus_mode and proposed_action.urgency.value != "critical"
        )
        if focus_mode_violated:
            applied_rules.append("FocusModeProtection")
            reasons.append("User is in focus mode; only critical actions allowed")

        # Step 3: Make decision
        # Advisory mode: chat responses never get null-vetoed for soft violations
        advisory_mode = (
            proposed_action.action_type == "chat_response"
            or proposed_action.metadata.get("advisory_only", False)
        )

        # Hard veto: topic filter + focus mode always block even in advisory mode
        hard_veto = (not topic_check.passed) or focus_mode_violated

        # Soft violations: manipulation, engagement, time boundaries
        soft_violated = (
            (not manipulation_check.passed)
            or (not engagement_check.passed)
            or (not time_check.passed)
        )

        if hard_veto:
            decision = ESLDecision(
                status=ESLDecisionStatus.VETOED,
                reason="; ".join(reasons),
                violated_values=violated_values,
                applied_rules=applied_rules,
                confidence=0.95,
            )

        elif soft_violated and not advisory_mode:
            # Non-advisory context: veto on any soft violation
            decision = ESLDecision(
                status=ESLDecisionStatus.VETOED,
                reason="; ".join(reasons),
                violated_values=violated_values,
                applied_rules=applied_rules,
                confidence=0.95,
            )

        elif soft_violated and advisory_mode:
            # Advisory mode: approve with warning — user always gets a response
            decision = ESLDecision(
                status=ESLDecisionStatus.APPROVED,
                reason=f"Advisory: {'; '.join(reasons)}",
                violated_values=[],
                applied_rules=applied_rules,
                confidence=0.7,
            )

        elif time_check.suggested_modification:
            # MODIFY the action (e.g., delay until appropriate time)
            decision = ESLDecision(
                status=ESLDecisionStatus.MODIFIED,
                reason=time_check.reason,
                modified_action=time_check.suggested_modification,
                violated_values=[],
                applied_rules=applied_rules,
                confidence=0.90,
            )

        else:
            # APPROVE the action
            decision = ESLDecision(
                status=ESLDecisionStatus.APPROVED,
                reason="Action aligns with user values and ethical guidelines",
                violated_values=[],
                applied_rules=applied_rules,
                confidence=0.95,
            )

        # Step 3b: Apply user-specific ESL sensitivity (E.1 — from value_conflict feedback)
        if decision.status == ESLDecisionStatus.APPROVED and not hard_veto:
            sensitivity = await self._get_user_sensitivity(
                user_id, proposed_action.content_type
            )
            if sensitivity > 0.3 and decision.confidence < 0.7:
                decision = ESLDecision(
                    status=ESLDecisionStatus.MODIFIED,
                    reason="Applying extra caution based on your previous feedback on this content type",
                    violated_values=[],
                    applied_rules=applied_rules + ["UserSensitivityBoost"],
                    confidence=0.75,
                )

        # Step 4: Audit log (mandatory)
        await self.audit_logger.log_decision(
            user_id=user_id,
            proposed_action=proposed_action,
            decision=decision,
            context_snapshot={
                "current_time": context.current_time.isoformat(),
                "focus_mode": context.focus_mode,
                "active_goals": context.active_goals,
                "user_values_count": len(context.user_values),
            },
        )

        return decision

    async def note_user_sensitivity(
        self, user_id: str, content_category: str, increment: float = 0.1
    ) -> None:
        """
        Record that a user flagged a content_category as value_conflict.
        Accumulates sensitivity_boost (capped at 1.0) in user_esl_sensitivity table.

        Args:
            user_id: User ID
            content_category: Content type/category that was flagged
            increment: How much to boost sensitivity (default 0.1)
        """
        from utils.db import get_db_connection

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO user_esl_sensitivity (user_id, content_category, sensitivity_boost)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, content_category)
                        DO UPDATE SET
                            sensitivity_boost = LEAST(user_esl_sensitivity.sensitivity_boost + %s, 1.0),
                            updated_at = NOW()
                        """,
                        (user_id, content_category, increment, increment),
                    )
                conn.commit()
            logger.info(
                f"[ESL] Sensitivity boost +{increment} for user={user_id} category={content_category}"
            )
        except Exception as e:
            logger.warning(f"Could not record ESL sensitivity for {user_id}: {e}")

    async def _get_user_sensitivity(self, user_id: str, content_category: str) -> float:
        """Return accumulated sensitivity boost for a user/category pair."""
        from utils.db import get_db_connection

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT sensitivity_boost FROM user_esl_sensitivity WHERE user_id = %s AND content_category = %s",  # noqa: E501
                        (user_id, content_category),
                    )
                    row = cur.fetchone()
            return float(row["sensitivity_boost"]) if row else 0.0
        except Exception:
            return 0.0

    async def check_content_safety(
        self, content: str, user_id: str, content_type: str = "general"
    ) -> "ContentSafetyCheck":
        """
        Check if content is safe to show based on user values

        THIS IS V2 INTEGRATION - Used by relevance scoring to filter unsafe content
        BEFORE showing it to the user.

        This is lighter than evaluate_action() because we're just checking if content
        violates user values, not deciding whether to take an action.

        Args:
            content: Content to check
            user_id: User ID
            content_type: Type of content (for context)

        Returns:
            ContentSafetyCheck with blocked status and reason
        """
        # Import here to avoid circular dependency
        from models.relevance import ContentSafetyCheck

        # Get user values
        user_values = await self.context_manager.get_user_values(user_id)

        # Check topic filters
        topic_check = self.topic_filter.check_topic_text(content, user_values)
        if not topic_check.passed:
            return ContentSafetyCheck(
                blocked=True,
                reason=topic_check.reason,
                violated_values=topic_check.violated_values,
                confidence=0.85,
            )

        # Check manipulation patterns
        manipulation_check = self.manipulation_detector.check_content(content)
        if not manipulation_check.passed:
            return ContentSafetyCheck(
                blocked=True,
                reason=f"Manipulation detected: {manipulation_check.reason}",
                violated_values=[],
                confidence=0.80,
            )

        # Content is safe
        return ContentSafetyCheck(
            blocked=False,
            reason="Content passes ethical checks",
            violated_values=[],
            confidence=0.90,
        )

    async def get_transparency_report(self, user_id: str, days: int = 7) -> dict:
        """
        Generate transparency report for a user

        Shows user how the ESL has been protecting them

        Args:
            user_id: User ID
            days: Number of days to include in report

        Returns:
            Dictionary with approval rate, vetoed actions, etc.
        """
        logs = await self.audit_logger.get_user_logs(user_id, days=days)

        total = len(logs)
        if total == 0:
            return {
                "total_decisions": 0,
                "approval_rate": 0.0,
                "vetoed_count": 0,
                "modified_count": 0,
                "message": "No decisions in the selected period",
            }

        approved = sum(
            1 for log in logs if log.decision.status == ESLDecisionStatus.APPROVED
        )
        vetoed = sum(
            1 for log in logs if log.decision.status == ESLDecisionStatus.VETOED
        )
        modified = sum(
            1 for log in logs if log.decision.status == ESLDecisionStatus.MODIFIED
        )

        return {
            "total_decisions": total,
            "approval_rate": approved / total,
            "approved_count": approved,
            "vetoed_count": vetoed,
            "modified_count": modified,
            "recent_vetoes": [
                {
                    "action_type": log.proposed_action.action_type,
                    "reason": log.decision.reason,
                    "timestamp": log.timestamp.isoformat(),
                }
                for log in logs[-5:]
                if log.decision.status == ESLDecisionStatus.VETOED
            ],
        }
