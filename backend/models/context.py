"""
Context Models

Models for user context, goals, and events
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class GoalStatus(str, Enum):
    """Status of a user goal"""

    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Goal(BaseModel):
    """User goal"""

    id: Optional[str] = None
    user_id: str
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    status: GoalStatus = GoalStatus.ACTIVE
    priority: int = Field(default=5, ge=1, le=10)
    target_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Launch MVP by end of Q1",
                "description": "Complete Ethic Companion MVP",
                "status": "active",
                "priority": 1,
            }
        }
    )


class Event(BaseModel):
    """Calendar event"""

    id: Optional[str] = None
    user_id: str
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    source: str = Field(
        ..., description="Source of event (google_calendar, manual, etc.)"
    )
    source_id: Optional[str] = Field(None, description="ID from external source")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Project Phoenix Meeting",
                "start_time": "2025-11-04T15:00:00Z",
                "end_time": "2025-11-04T16:00:00Z",
                "source": "google_calendar",
            }
        }
    )


class ConversationMessage(BaseModel):
    """Message in a conversation"""

    id: Optional[str] = None
    user_id: str
    role: str = Field(..., description="user or assistant")
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SemanticMemoryEntry(BaseModel):
    """Entry in semantic memory (M2)"""

    id: Optional[str] = None
    user_id: str
    content: str
    embedding: Optional[list[float]] = None
    source: str = Field(
        ..., description="Source of content (conversation, note, calendar)"
    )
    source_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
