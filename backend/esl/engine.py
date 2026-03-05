"""
Ethical Safeguard Layer - Core Engine

The heart of Ethic Companion's ethical decision-making system.

This class is the MANDATORY GATEWAY for all user-facing actions.
No action can bypass this evaluation.
"""

from typing import Optional
from datetime import datetime

from .models import (
    ProposedAction,
    ESLDecision,
    ESLDecisionStatus,
    UserContext,
    UserValue,
)
from .rules import TimeBasedRules, ManipulationDetector, EngagementDetector, TopicFilter
from .audit import ESLAuditLogger


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
    
    def __init__(self, context_manager, audit_logger: Optional[ESLAuditLogger] = None, db_connection_factory=None):
        """
        Initialize the ESL

        Args:
            context_manager: ContextManager instance for retrieving user context
            audit_logger: ESLAuditLogger instance for logging decisions
            db_connection_factory: Optional callable for database connections (enables audit persistence)
        """
        self.context_manager = context_manager
        # Use provided audit_logger, or create one with optional database persistence
        self.audit_logger = audit_logger or ESLAuditLogger(db_connection_factory=db_connection_factory)
        
        # Initialize rule checkers
        self.time_rules = TimeBasedRules()
        self.manipulation_detector = ManipulationDetector()
        self.engagement_detector = EngagementDetector()
        self.topic_filter = TopicFilter()
    
    async def evaluate_action(
        self,
        proposed_action: ProposedAction,
        user_id: str
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
            proposed_action,
            context.user_values,
            context.current_time
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
        
        # Check 3: Engagement vs. Assistance intent
        engagement_check = self.engagement_detector.check_intent(proposed_action)
        if not engagement_check.passed:
            applied_rules.append("EngagementDetector")
            reasons.append(engagement_check.reason)
        
        # Check 4: Topic filter violations
        topic_check = self.topic_filter.check_topic(
            proposed_action,
            context.user_values
        )
        if not topic_check.passed:
            violated_values.extend(topic_check.violated_values)
            applied_rules.append("TopicFilter")
            reasons.append(topic_check.reason)

        # Check 5: Focus mode respect
        focus_mode_violated = context.focus_mode and proposed_action.urgency.value != "critical"
        if focus_mode_violated:
            applied_rules.append("FocusModeProtection")
            reasons.append("User is in focus mode; only critical actions allowed")

        # Step 3: Make decision
        if violated_values or not manipulation_check.passed or not engagement_check.passed or not topic_check.passed or focus_mode_violated:
            # VETO the action
            decision = ESLDecision(
                status=ESLDecisionStatus.VETOED,
                reason="; ".join(reasons),
                violated_values=violated_values,
                applied_rules=applied_rules,
                confidence=0.95
            )
        
        elif time_check.suggested_modification:
            # MODIFY the action (e.g., delay until appropriate time)
            decision = ESLDecision(
                status=ESLDecisionStatus.MODIFIED,
                reason=time_check.reason,
                modified_action=time_check.suggested_modification,
                violated_values=[],
                applied_rules=applied_rules,
                confidence=0.90
            )
        
        else:
            # APPROVE the action
            decision = ESLDecision(
                status=ESLDecisionStatus.APPROVED,
                reason="Action aligns with user values and ethical guidelines",
                violated_values=[],
                applied_rules=applied_rules,
                confidence=0.95
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
                "user_values_count": len(context.user_values)
            }
        )
        
        return decision
    
    async def check_content_safety(
        self,
        content: str,
        user_id: str,
        content_type: str = "general"
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
                confidence=0.85
            )

        # Check manipulation patterns
        manipulation_check = self.manipulation_detector.check_content(content)
        if not manipulation_check.passed:
            return ContentSafetyCheck(
                blocked=True,
                reason=f"Manipulation detected: {manipulation_check.reason}",
                violated_values=[],
                confidence=0.80
            )

        # Content is safe
        return ContentSafetyCheck(
            blocked=False,
            reason="Content passes ethical checks",
            violated_values=[],
            confidence=0.90
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
                "message": "No decisions in the selected period"
            }

        approved = sum(1 for log in logs if log.decision.status == ESLDecisionStatus.APPROVED)
        vetoed = sum(1 for log in logs if log.decision.status == ESLDecisionStatus.VETOED)
        modified = sum(1 for log in logs if log.decision.status == ESLDecisionStatus.MODIFIED)

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
                    "timestamp": log.timestamp.isoformat()
                }
                for log in logs[-5:] if log.decision.status == ESLDecisionStatus.VETOED
            ]
        }
