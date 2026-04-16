"""
ESL Data Models

Pydantic models for the Ethical Safeguard Layer
These models define the core data structures for ethical decision-making
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Annotated, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ESLDecisionStatus(str, Enum):
    """Status of an ESL decision"""

    APPROVED = "APPROVED"  # Action is ethical and approved
    VETOED = "VETOED"  # Action violates boundaries, blocked
    MODIFIED = "MODIFIED"  # Action modified to be ethical


class ActionType(str, Enum):
    """Types of actions that require ESL evaluation"""

    PUSH_NOTIFICATION = "push_notification"
    EMAIL_SEND = "email_send"
    SLACK_SEND = "slack_send"
    CONTENT_GENERATION = "content_generation"
    PROACTIVE_SUMMARY = "proactive_summary"
    REMINDER = "reminder"
    CALENDAR_WRITE = "calendar_write"
    DATA_COLLECTION = "data_collection"
    CHAT_RESPONSE = "chat_response"
    VOICE_OUTPUT = "voice_output"


class UrgencyLevel(str, Enum):
    """Urgency levels for proposed actions"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ValueType(str, Enum):
    """Types of user values"""

    BOUNDARY = "boundary"  # Hard limits (e.g., "no work after 7pm")
    PREFERENCE = "preference"  # Soft preferences (e.g., "prefer morning summaries")
    TOPIC_FILTER = "topic_filter"  # Content filters (e.g., "no politics")
    TIME_WINDOW = "time_window"  # Time-based rules


class ProposedAction(BaseModel):
    """
    An action proposed by the Orchestrator that requires ESL evaluation

    Example:
        ProposedAction(
            action_type="push_notification",
            content_type="work_summary",
            urgency="medium",
            content="Summary of Project Phoenix meeting",
            metadata={"meeting_id": "123", "category": "work"}
        )
    """

    action_type: ActionType
    content_type: str = Field(
        ..., description="Type of content (work_summary, reminder, etc.)"
    )
    urgency: UrgencyLevel
    content: Annotated[
        Optional[str], Field(description="The actual content/message")
    ] = None
    target_time: Annotated[
        Optional[datetime], Field(description="When to execute the action")
    ] = None
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action_type": "push_notification",
                "content_type": "work_summary",
                "urgency": "medium",
                "content": "Your meeting starts in 15 minutes",
                "metadata": {"meeting_id": "abc123"},
            }
        }
    )


class UserValue(BaseModel):
    """
    User-defined value or boundary

    These are SACRED - the ESL must enforce them without exception

    Example:
        UserValue(
            type="boundary",
            value="no_work_after_19h",
            priority=1,
            active=True
        )
    """

    id: Optional[str] = None
    user_id: str
    type: ValueType
    value: str = Field(
        ..., description="The boundary/preference in human-readable form"
    )
    priority: int = Field(..., ge=1, le=10, description="Priority level (1=highest)")
    active: bool = Field(
        default=True, description="Whether this value is currently active"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user_123",
                "type": "boundary",
                "value": "no_work_after_19h",
                "priority": 1,
                "active": True,
            }
        }
    )


class ESLDecision(BaseModel):
    """
    Decision made by the Ethical Safeguard Layer

    This is the output of esl.evaluate_action()
    """

    status: ESLDecisionStatus
    reason: str = Field(..., description="Human-readable explanation of the decision")
    modified_action: Annotated[
        Optional[ProposedAction],
        Field(description="If status=MODIFIED, this contains the modified action"),
    ] = None
    violated_values: list[str] = Field(
        default_factory=list, description="IDs of user values that would be violated"
    )
    applied_rules: list[str] = Field(
        default_factory=list, description="Names of ESL rules that were applied"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the decision"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "VETOED",
                "reason": "Violates user boundary: no_work_after_19h",
                "violated_values": ["value_123"],
                "applied_rules": ["TimeBasedRules.check_work_hours"],
                "confidence": 0.95,
            }
        }
    )


class ESLAuditLog(BaseModel):
    """
    Audit log entry for ESL decisions

    Every ESL decision MUST be logged for:
    1. Transparency to users
    2. Ethical research
    3. System improvement
    """

    id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: str
    proposed_action: ProposedAction
    decision: ESLDecision
    context_snapshot: Dict[str, Any] = Field(
        default_factory=dict, description="Snapshot of user context at decision time"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user_123",
                "proposed_action": {
                    "action_type": "push_notification",
                    "content_type": "work_summary",
                    "urgency": "medium",
                },
                "decision": {
                    "status": "APPROVED",
                    "reason": "Within user's work hours and relevant to goals",
                },
                "context_snapshot": {"current_time": "14:30", "focus_mode": False},
            }
        }
    )


class UserContext(BaseModel):
    """
    Current user context for ESL evaluation

    This is retrieved from the Context Manager
    """

    user_id: str
    current_time: datetime = Field(default_factory=datetime.utcnow)
    focus_mode: bool = Field(default=False, description="Is user in focus mode?")
    active_goals: list[str] = Field(default_factory=list, description="Active goal IDs")
    recent_interactions: list[Dict[str, Any]] = Field(
        default_factory=list, description="Recent user interactions"
    )
    user_values: list[UserValue] = Field(default_factory=list)
    additional_context: Dict[str, Any] = Field(default_factory=dict)
