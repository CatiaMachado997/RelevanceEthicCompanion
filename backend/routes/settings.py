"""
Settings API Routes

User preferences that inform ESL and app behaviour.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from utils.db import get_db
from utils.serialization import serialize_row
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from services.context_manager import ContextManager
from esl.engine import EthicalSafeguardLayer
from esl.models import ProposedAction, ActionType, UrgencyLevel, ESLDecisionStatus

router = APIRouter(prefix="/api/settings", tags=["Settings"])

DEFAULTS = {
    "email_notifications": False,
    "push_notifications": False,
    "esl_alerts": True,
    "share_analytics": False,
    "pii_protection": True,
    "weight_goal_alignment": 1.0,
    "weight_time_sensitivity": 1.0,
    "weight_personal_values": 1.0,
    "weight_context_relevance": 1.0,
}


def get_context_manager() -> ContextManager:
    return ContextManager()


def get_esl(context_manager: ContextManager = Depends(get_context_manager)) -> EthicalSafeguardLayer:
    return EthicalSafeguardLayer(context_manager)


class UpdateSettingsRequest(BaseModel):
    email_notifications: bool = False
    push_notifications: bool = False
    esl_alerts: bool = True
    share_analytics: bool = False
    pii_protection: bool = True
    weight_goal_alignment: float = 1.0
    weight_time_sensitivity: float = 1.0
    weight_personal_values: float = 1.0
    weight_context_relevance: float = 1.0
    timezone: Optional[str] = None
    language: Optional[str] = None


@router.get("/", response_model=dict)
async def get_settings(
    user_id: str = Depends(get_current_user_id),
):
    """Fetch user settings. Returns defaults if no row exists yet."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM user_settings WHERE user_id = %s",
                    (str(user_id),),
                )
                row = cur.fetchone()

        data = serialize_row(row) if row else {**DEFAULTS, "user_id": str(user_id)}
        # Ensure weight fields are always present (handles DB rows created before migration)
        for key, default in [
            ("weight_goal_alignment", 1.0), ("weight_time_sensitivity", 1.0),
            ("weight_personal_values", 1.0), ("weight_context_relevance", 1.0),
        ]:
            if key not in data or data[key] is None:
                data[key] = default
        return {"status": "success", "data": data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching settings: {str(e)}")


@router.put("/", response_model=dict)
async def update_settings(
    request: UpdateSettingsRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """Upsert user settings. ESL-gated."""
    try:
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="settings_update",
            content=f"Updating settings for user {user_id}",
            urgency=UrgencyLevel.LOW,
            metadata=request.model_dump(),
        )
        decision = await esl.evaluate_action(proposed_action, user_id)

        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(
                status_code=403,
                detail=f"Settings update blocked by ESL: {decision.reason}",
            )

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_settings
                        (user_id, email_notifications, push_notifications,
                         esl_alerts, share_analytics, pii_protection,
                         weight_goal_alignment, weight_time_sensitivity,
                         weight_personal_values, weight_context_relevance,
                         timezone, language)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        email_notifications      = EXCLUDED.email_notifications,
                        push_notifications       = EXCLUDED.push_notifications,
                        esl_alerts               = EXCLUDED.esl_alerts,
                        share_analytics          = EXCLUDED.share_analytics,
                        pii_protection           = EXCLUDED.pii_protection,
                        weight_goal_alignment    = EXCLUDED.weight_goal_alignment,
                        weight_time_sensitivity  = EXCLUDED.weight_time_sensitivity,
                        weight_personal_values   = EXCLUDED.weight_personal_values,
                        weight_context_relevance = EXCLUDED.weight_context_relevance,
                        timezone                 = COALESCE(EXCLUDED.timezone, user_settings.timezone),
                        language                 = COALESCE(EXCLUDED.language, user_settings.language),
                        updated_at               = NOW()
                    RETURNING *
                    """,
                    (
                        str(user_id),
                        request.email_notifications,
                        request.push_notifications,
                        request.esl_alerts,
                        request.share_analytics,
                        request.pii_protection,
                        request.weight_goal_alignment,
                        request.weight_time_sensitivity,
                        request.weight_personal_values,
                        request.weight_context_relevance,
                        request.timezone,
                        request.language,
                    ),
                )
                saved = cur.fetchone()

        return {
            "status": "success",
            "message": "Settings saved successfully",
            "data": serialize_row(saved),
        }

    except HTTPException:
        raise
    except Exception as e:
        err = str(e)
        if "column" in err and "does not exist" in err:
            raise HTTPException(
                status_code=500,
                detail="Database schema is out of date. Restart the backend to apply migrations.",
            )
        raise HTTPException(status_code=500, detail=f"Error saving settings: {err}")
