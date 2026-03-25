"""Feedback API Routes"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from utils.supabase_auth import get_current_user_id
from services.feedback_processor import FeedbackProcessor
from models.feedback import FeedbackSubmission, FeedbackType, ItemType

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])


def get_feedback_processor() -> FeedbackProcessor:
    return FeedbackProcessor()


@router.post("/", response_model=dict)
async def submit_feedback(
    request: FeedbackSubmission,
    user_id: str = Depends(get_current_user_id),
    processor: FeedbackProcessor = Depends(get_feedback_processor),
):
    """Submit feedback on an AI response or content item."""
    try:
        result = await processor.submit_feedback(
            user_id=str(user_id),
            item_id=request.item_id,
            item_type=request.item_type,
            feedback_type=request.feedback_type,
            additional_notes=request.additional_notes,
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting feedback: {str(e)}")
