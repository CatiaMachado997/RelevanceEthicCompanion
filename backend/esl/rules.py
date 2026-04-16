"""
ESL Rule System

Individual rule checkers for the Ethical Safeguard Layer
Each rule is testable and auditable
"""

from typing import Optional, List, Dict
from datetime import datetime, time
from pydantic import BaseModel
import re
import hashlib

from .models import ProposedAction, UserValue, ValueType

# Module-level cache for semantic manipulation check results (keyed by content hash)
_semantic_cache: Dict[str, bool] = {}


async def semantic_manipulation_check(content: str, llm) -> bool:
    """
    LLM-based secondary manipulation check.

    Only invoked for content > 100 chars. Results are cached per content hash
    to avoid redundant LLM calls.

    Args:
        content: Text to evaluate
        llm: LangChain LLM instance (must support ainvoke)

    Returns:
        True if the LLM considers the content manipulative
    """
    if len(content) < 100:
        return False

    content_hash = hashlib.sha256(content[:500].encode()).hexdigest()[:16]
    if content_hash in _semantic_cache:
        return _semantic_cache[content_hash]

    try:
        from langchain_core.messages import HumanMessage

        prompt = (
            "Evaluate if this content uses psychological manipulation "
            "(FOMO, guilt, false urgency, social pressure, emotional coercion):\n\n"
            f'Content: "{content[:500]}"\n\n'
            "Answer only: YES or NO"
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        is_manipulative = "YES" in response.content.upper()
        _semantic_cache[content_hash] = is_manipulative
        return is_manipulative
    except Exception:
        return False


class RuleCheckResult(BaseModel):
    """Result of a rule check"""

    passed: bool
    reason: str
    violated_values: List[str] = []
    suggested_modification: Optional[ProposedAction] = None


class TimeBasedRules:
    """
    Time-based boundary checking

    Enforces user-defined time boundaries like:
    - "No work after 7 PM"
    - "Quiet hours 10 PM - 7 AM"
    - "Focus mode 9 AM - 11 AM"
    """

    def check_boundaries(
        self,
        action: ProposedAction,
        user_values: List[UserValue],
        current_time: datetime,
    ) -> RuleCheckResult:
        """
        Check if action violates time-based boundaries

        Args:
            action: Proposed action
            user_values: User's values and boundaries
            current_time: Current timestamp

        Returns:
            RuleCheckResult with pass/fail and reason
        """
        current_hour = current_time.hour

        for value in user_values:
            if not value.active or value.type != ValueType.BOUNDARY:
                continue

            # Check "no_work_after_Xh" patterns
            if "no_work_after" in value.value.lower():
                match = re.search(r"after[_\s](\d+)", value.value)
                if match:
                    cutoff_hour = int(match.group(1))
                    if (
                        current_hour >= cutoff_hour
                        and "work" in action.content_type.lower()
                    ):
                        # Suggest modification: queue for next morning
                        return RuleCheckResult(
                            passed=False,
                            reason=f"Violates user boundary: {value.value}",
                            violated_values=[value.id or value.value],
                            suggested_modification=None,  # Could suggest "queue_for_morning"
                        )

            # Check "quiet_hours" patterns
            if (
                "quiet_hours" in value.value.lower()
                or "do_not_disturb" in value.value.lower()
            ):
                # Assume quiet hours are 22:00 - 07:00
                if current_hour >= 22 or current_hour < 7:
                    return RuleCheckResult(
                        passed=False,
                        reason=f"Violates quiet hours: {value.value}",
                        violated_values=[value.id or value.value],
                    )

        return RuleCheckResult(passed=True, reason="No time-based boundary violations")


class ManipulationDetector:
    """
    Detects psychological manipulation patterns

    Blocks content that uses:
    - FOMO (Fear of Missing Out)
    - Artificial urgency
    - Guilt-tripping
    - Emotional manipulation
    """

    # Manipulation pattern keywords
    FOMO_PATTERNS = [
        r"don't miss out",
        r"last chance",
        r"everyone else",
        r"you're missing",
        r"limited time",
        r"act now",
        r"before it's gone",
    ]

    URGENCY_PATTERNS = [
        r"urgent(?!.*meeting)",  # "urgent" but not "urgent meeting"
        r"act immediately",
        r"right now",
        r"can't wait",
    ]

    GUILT_PATTERNS = [
        r"you should have",
        r"you forgot",
        r"you haven't",
        r"disappointing",
    ]

    def check_content(self, content: str) -> RuleCheckResult:
        """
        Check if content contains manipulation patterns.
        Requires ≥2 distinct manipulation signals before flagging.

        Args:
            content: Text content to check

        Returns:
            RuleCheckResult with pass/fail
        """
        if not content:
            return RuleCheckResult(passed=True, reason="No content to check")

        content_lower = content.lower()
        violations = []

        # Check FOMO patterns
        for pattern in self.FOMO_PATTERNS:
            if re.search(pattern, content_lower):
                violations.append(f"FOMO: '{pattern}'")

        # Check urgency abuse (not genuine urgency)
        for pattern in self.URGENCY_PATTERNS:
            if re.search(pattern, content_lower):
                violations.append(f"urgency: '{pattern}'")

        # Check guilt patterns
        for pattern in self.GUILT_PATTERNS:
            if re.search(pattern, content_lower):
                violations.append(f"guilt: '{pattern}'")

        if len(violations) >= 2:
            return RuleCheckResult(
                passed=False,
                reason=f"Detected multiple manipulation patterns: {'; '.join(violations)}",
            )

        return RuleCheckResult(passed=True, reason="No manipulation patterns detected")


class EngagementDetector:
    """
    Detects engagement-optimization intent vs. assistance intent

    Rejects actions that optimize for metrics like:
    - Time in app
    - Click-through rate
    - Daily active usage

    Approves actions that optimize for:
    - Goal completion
    - User well-being
    - Clarity and focus
    """

    def check_intent(self, action: ProposedAction) -> RuleCheckResult:
        """
        Check if action intent is assistance vs. engagement.
        Only flags when engagement score is strong (>0.7) AND no assistance signals.

        Args:
            action: Proposed action

        Returns:
            RuleCheckResult with pass/fail
        """
        metadata = action.metadata

        # Red flags: action optimized for engagement
        engagement_metrics = [
            "click_rate",
            "time_in_app",
            "daily_active",
            "session_length",
            "retention_boost",
        ]

        # Green flags: action optimized for assistance
        assistance_metrics = [
            "goal_relevance",
            "user_request",
            "time_saving",
            "clarity_improvement",
        ]

        engagement_count = sum(1 for m in engagement_metrics if m in metadata)
        engagement_score = engagement_count / len(engagement_metrics)
        goal_relevance_score = (
            1.0 if any(m in metadata for m in assistance_metrics) else 0.0
        )

        # Only flag if engagement signals are strong AND no positive assistance signals
        if engagement_score > 0.7 and goal_relevance_score < 0.3:
            return RuleCheckResult(
                passed=False,
                reason=f"Action strongly optimized for engagement metrics (score: {engagement_score:.1f}) without assistance intent",
            )

        # High urgency without any assistance intent is suspicious
        if action.urgency.value == "critical" and goal_relevance_score < 0.3:
            return RuleCheckResult(
                passed=False,
                reason="High urgency without clear assistance intent (possible manipulation)",
            )

        return RuleCheckResult(
            passed=True, reason="Action intent aligned with user assistance"
        )


class TopicFilter:
    """
    Filters content by topic based on user preferences

    Blocks topics user has explicitly requested to avoid:
    - Politics
    - Specific work projects
    - Certain categories
    """

    def check_topic(
        self, action: ProposedAction, user_values: List[UserValue]
    ) -> RuleCheckResult:
        """
        Check if action topic violates user filters

        Args:
            action: Proposed action
            user_values: User's topic filters

        Returns:
            RuleCheckResult with pass/fail
        """
        content = (action.content or "").lower()
        content_type = action.content_type.lower()

        for value in user_values:
            if not value.active or value.type != ValueType.TOPIC_FILTER:
                continue

            # Extract blocked topic
            blocked_topic = value.value.lower().replace("no_", "").replace("_", " ")

            if blocked_topic in content or blocked_topic in content_type:
                return RuleCheckResult(
                    passed=False,
                    reason=f"Content violates topic filter: {value.value}",
                    violated_values=[value.id or value.value],
                )

        return RuleCheckResult(passed=True, reason="No topic filter violations")

    def check_topic_text(
        self, content: str, user_values: List[UserValue]
    ) -> RuleCheckResult:
        """
        Check if raw text content violates user topic filters

        V2 INTEGRATION - Used by relevance scoring to check content
        before deciding if it's safe to show.

        Args:
            content: Raw text to check
            user_values: User's topic filters

        Returns:
            RuleCheckResult with pass/fail
        """
        content_lower = content.lower()

        for value in user_values:
            if not value.active or value.type != ValueType.TOPIC_FILTER:
                continue

            # Extract blocked topic
            blocked_topic = value.value.lower().replace("no_", "").replace("_", " ")

            if blocked_topic in content_lower:
                return RuleCheckResult(
                    passed=False,
                    reason=f"Content contains blocked topic: {blocked_topic}",
                    violated_values=[value.id or value.value],
                )

        return RuleCheckResult(passed=True, reason="No topic filter violations")
