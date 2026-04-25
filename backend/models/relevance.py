"""
Relevance Models
Data models for V2 relevance scoring system
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ItemType(str, Enum):
    """Types of items that can be scored for relevance"""

    SEARCH_RESULT = "search_result"
    MEMORY = "memory"
    CALENDAR_EVENT = "calendar_event"
    SUMMARY = "summary"
    PROACTIVE_SUGGESTION = "proactive_suggestion"
    WEB_CONTENT = "web_content"


class CandidateItem(BaseModel):
    """
    Item to be scored for relevance

    This represents any piece of content that could be shown to the user.
    The relevance engine scores these items based on custom algorithms.
    """

    id: str = Field(description="Unique identifier for the item")
    type: ItemType = Field(description="Type of item")
    content: str = Field(description="Main content text")
    title: Optional[str] = Field(None, description="Optional title")
    source: str = Field(
        description="Source of the item (e.g., 'tavily', 'weaviate', 'google_calendar')"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When item was created/retrieved"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ScoredItem(BaseModel):
    """
    Item with relevance score and explanation

    After scoring, this is what we return to show the user.
    The explanation is critical for transparency.
    """

    item: CandidateItem = Field(description="The original item")
    relevance_score: float = Field(description="Computed relevance score (0-100)")
    explanation: str = Field(
        description="Human-readable explanation of why this is relevant"
    )
    score_breakdown: Dict[str, float] = Field(
        default_factory=dict, description="Breakdown of score components"
    )
    ethical_flags: List[str] = Field(
        default_factory=list, description="Any ethical concerns raised by ESL"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in the score (0-1)"
    )


class RelevanceContext(BaseModel):
    """
    Context used for relevance scoring

    This is what we pass to the scoring engine to make decisions.
    """

    user_id: str = Field(description="Supabase UUID")
    query: Optional[str] = Field(None, description="User's query if any")
    active_goals: List[str] = Field(
        default_factory=list, description="List of active goal titles"
    )
    upcoming_events: List[Dict[str, Any]] = Field(
        default_factory=list, description="Upcoming calendar events"
    )
    recent_topics: List[str] = Field(
        default_factory=list, description="Recently discussed topics"
    )
    focus_mode: bool = Field(default=False, description="Is user in focus mode?")
    user_values: List[str] = Field(
        default_factory=list, description="User's ethical values"
    )
    time_of_day: int = Field(default=12, ge=0, le=23, description="Current hour (0-23)")


class FeedbackType(str, Enum):
    """Types of user feedback"""

    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    DISMISS = "dismiss"
    ENGAGE = "engage"


class RelevanceFeedback(BaseModel):
    """
    User feedback on an item's relevance

    Stored for future ML training (not in MVP, but structure is ready)
    """

    id: Optional[str] = None
    user_id: str = Field(description="Supabase UUID")
    item_id: str = Field(description="ID of the item that was shown")
    item_type: ItemType = Field(description="Type of item")
    feedback_type: FeedbackType = Field(description="Type of feedback")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context_snapshot: Dict[str, Any] = Field(
        default_factory=dict, description="Context when feedback was given"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ContentSafetyCheck(BaseModel):
    """
    Result of ESL content safety check

    Used by relevance scoring to filter out unsafe content
    """

    blocked: bool = Field(description="Should this content be blocked?")
    reason: Optional[str] = Field(None, description="Reason for blocking")
    violated_values: List[str] = Field(
        default_factory=list, description="Which user values were violated"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in the decision"
    )
