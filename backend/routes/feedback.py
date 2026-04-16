"""Feedback API Routes"""

from fastapi import APIRouter, HTTPException, Depends

from utils.supabase_auth import get_current_user_id
from services.feedback_processor import FeedbackProcessor
from models.feedback import FeedbackSubmission

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
        # Close the feedback loop: nudge relevance weights based on patterns
        await processor.adjust_signal_from_feedback(
            user_id=str(user_id),
            feedback_type=request.feedback_type,
            item_type=request.item_type,
        )
        # E.1: value_conflict → increase ESL sensitivity for this content category
        if request.feedback_type == "value_conflict":
            await processor.note_esl_sensitivity_boost(
                user_id=str(user_id),
                content_category=request.item_type,
            )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error submitting feedback: {str(e)}"
        )
