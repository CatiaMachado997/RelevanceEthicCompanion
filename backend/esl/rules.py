"""
ESL Rule System

Individual rule checkers for the Ethical Safeguard Layer
Each rule is testable and auditable
"""

from typing import Optional, List
from datetime import datetime, time
from pydantic import BaseModel
import re

from .models import ProposedAction, UserValue, ValueType


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
        current_time: datetime
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
                match = re.search(r'after[_\s](\d+)', value.value)
                if match:
                    cutoff_hour = int(match.group(1))
                    if current_hour >= cutoff_hour and "work" in action.content_type.lower():
                        # Suggest modification: queue for next morning
                        return RuleCheckResult(
                            passed=False,
                            reason=f"Violates user boundary: {value.value}",
                            violated_values=[value.id or value.value],
                            suggested_modification=None  # Could suggest "queue_for_morning"
                        )
            
            # Check "quiet_hours" patterns
            if "quiet_hours" in value.value.lower() or "do_not_disturb" in value.value.lower():
                # Assume quiet hours are 22:00 - 07:00
                if current_hour >= 22 or current_hour < 7:
                    return RuleCheckResult(
                        passed=False,
                        reason=f"Violates quiet hours: {value.value}",
                        violated_values=[value.id or value.value]
                    )
        
        return RuleCheckResult(
            passed=True,
            reason="No time-based boundary violations"
        )


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
        r"before it's gone"
    ]
    
    URGENCY_PATTERNS = [
        r"urgent(?!.*meeting)",  # "urgent" but not "urgent meeting"
        r"act immediately",
        r"right now",
        r"can't wait"
    ]
    
    GUILT_PATTERNS = [
        r"you should have",
        r"you forgot",
        r"you haven't",
        r"disappointing"
    ]
    
    def check_content(self, content: str) -> RuleCheckResult:
        """
        Check if content contains manipulation patterns
        
        Args:
            content: Text content to check
            
        Returns:
            RuleCheckResult with pass/fail
        """
        if not content:
            return RuleCheckResult(passed=True, reason="No content to check")
        
        content_lower = content.lower()
        
        # Check FOMO patterns
        for pattern in self.FOMO_PATTERNS:
            if re.search(pattern, content_lower):
                return RuleCheckResult(
                    passed=False,
                    reason=f"Detected FOMO manipulation pattern: '{pattern}'"
                )
        
        # Check urgency abuse (not genuine urgency)
        for pattern in self.URGENCY_PATTERNS:
            if re.search(pattern, content_lower):
                return RuleCheckResult(
                    passed=False,
                    reason=f"Detected artificial urgency pattern: '{pattern}'"
                )
        
        # Check guilt patterns
        for pattern in self.GUILT_PATTERNS:
            if re.search(pattern, content_lower):
                return RuleCheckResult(
                    passed=False,
                    reason=f"Detected guilt-tripping pattern: '{pattern}'"
                )
        
        return RuleCheckResult(
            passed=True,
            reason="No manipulation patterns detected"
        )


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
        Check if action intent is assistance vs. engagement
        
        Args:
            action: Proposed action
            
        Returns:
            RuleCheckResult with pass/fail
        """
        # Check metadata for engagement metrics (anti-pattern)
        metadata = action.metadata
        
        # Red flags: action optimized for engagement
        engagement_metrics = [
            "click_rate",
            "time_in_app",
            "daily_active",
            "session_length",
            "retention_boost"
        ]
        
        for metric in engagement_metrics:
            if metric in metadata:
                return RuleCheckResult(
                    passed=False,
                    reason=f"Action optimized for engagement metric: {metric}"
                )
        
        # Green flags: action optimized for assistance
        assistance_metrics = [
            "goal_relevance",
            "user_request",
            "time_saving",
            "clarity_improvement"
        ]
        
        has_assistance_intent = any(metric in metadata for metric in assistance_metrics)
        
        # If action has very high urgency without clear assistance intent, be suspicious
        if action.urgency.value == "critical" and not has_assistance_intent:
            return RuleCheckResult(
                passed=False,
                reason="High urgency without clear assistance intent (possible manipulation)"
            )
        
        return RuleCheckResult(
            passed=True,
            reason="Action intent aligned with user assistance"
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
        self,
        action: ProposedAction,
        user_values: List[UserValue]
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
                    violated_values=[value.id or value.value]
                )
        
        return RuleCheckResult(
            passed=True,
            reason="No topic filter violations"
        )

    def check_topic_text(
        self,
        content: str,
        user_values: List[UserValue]
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
                    violated_values=[value.id or value.value]
                )

        return RuleCheckResult(
            passed=True,
            reason="No topic filter violations"
        )
