"""
Feedback Data Models

Models for user feedback on content and AI responses.
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class FeedbackType(str, Enum):
    """Types of feedback users can provide"""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    NOT_RELEVANT = "not_relevant"
    VALUE_CONFLICT = "value_conflict"
    INACCURATE = "inaccurate"


class ItemType(str, Enum):
    """Types of items that can receive feedback"""
    CHAT_RESPONSE = "chat_response"
    SEARCH_RESULT = "search_result"
    CALENDAR_EVENT = "calendar_event"
    PROACTIVE_INSIGHT = "proactive_insight"
    MEMORY_RECALL = "memory_recall"


class FeedbackSubmission(BaseModel):
    """User feedback submission"""
    item_id: str = Field(..., description="ID of the item being rated")
    item_type: ItemType = Field(..., description="Type of item")
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    additional_notes: Optional[str] = Field(None, description="Optional user notes")

    class Config:
        json_schema_extra = {
            "example": {
                "item_id": "response-123",
                "item_type": "chat_response",
                "feedback_type": "thumbs_up",
                "additional_notes": "Very helpful response!"
            }
        }


class FeedbackRecord(BaseModel):
    """Stored feedback record"""
    id: str
    user_id: str
    item_id: str
    item_type: ItemType
    feedback_type: FeedbackType
    context_snapshot: Dict[str, Any] = Field(default_factory=dict)
    additional_notes: Optional[str] = None
    timestamp: datetime


class FeedbackAnalytics(BaseModel):
    """Aggregated feedback analytics"""
    thumbs_up_count: int = 0
    thumbs_down_count: int = 0
    not_relevant_count: int = 0
    value_conflict_count: int = 0
    inaccurate_count: int = 0
    total_feedback: int = 0
    satisfaction_rate: float = 0.0
    days_analyzed: int = 30

    class Config:
        json_schema_extra = {
            "example": {
                "thumbs_up_count": 45,
                "thumbs_down_count": 5,
                "not_relevant_count": 2,
                "value_conflict_count": 1,
                "inaccurate_count": 1,
                "total_feedback": 54,
                "satisfaction_rate": 83.3,
                "days_analyzed": 30
            }
        }
