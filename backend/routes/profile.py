"""Profile API Routes"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel

from utils.db import get_db
from utils.serialization import serialize_row
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from services.context_manager import ContextManager
from esl.engine import EthicalSafeguardLayer
from esl.models import ProposedAction, ActionType, UrgencyLevel, ESLDecisionStatus

router = APIRouter(prefix="/api/profile", tags=["Profile"])


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    timezone: Optional[str] = None


def get_context_manager() -> ContextManager:
    return ContextManager()


def get_esl(
    context_manager: ContextManager = Depends(get_context_manager),
) -> EthicalSafeguardLayer:
    return EthicalSafeguardLayer(context_manager)


@router.get("/", response_model=dict)
async def get_profile(user_id: str = Depends(get_current_read_user_id)):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, display_name, timezone FROM users WHERE id = %s",
                    (str(user_id),),
                )
                user = cur.fetchone()
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM user_values WHERE user_id = %s AND active = TRUE",
                    (str(user_id),),
                )
                row = cur.fetchone()
                values_count = row.get("cnt", 0) if row is not None else 0

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM goals WHERE user_id = %s AND status = 'active'",
                    (str(user_id),),
                )
                row = cur.fetchone()
                goals_count = row.get("cnt", 0) if row is not None else 0

                cur.execute(
                    """
                    SELECT
                      COUNT(*) FILTER (WHERE decision_status = 'APPROVED') AS approved,
                      COUNT(*) AS total
                    FROM esl_audit_log WHERE user_id = %s
                    """,
                    (str(user_id),),
                )
                row = cur.fetchone() or {}
                total = row.get("total") or 0
                approved = row.get("approved") or 0
                approval_rate = round(approved / total, 2) if total > 0 else 0.0

        result = serialize_row(user)
        result["stats"] = {
            "values_count": values_count,
            "goals_count": goals_count,
            "approval_rate": approval_rate,
        }
        return {"status": "success", "data": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profile: {str(e)}")


@router.put("/", response_model=dict)
async def update_profile(
    request: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    proposed_action = ProposedAction(
        action_type=ActionType.DATA_COLLECTION,
        content_type="profile_update",
        content="Updating user profile",
        urgency=UrgencyLevel.LOW,
        metadata={"user_id": str(user_id)},
    )
    decision = await esl.evaluate_action(proposed_action, user_id)
    if decision.status == ESLDecisionStatus.VETOED:
        raise HTTPException(
            status_code=403, detail=f"Profile update blocked by ESL: {decision.reason}"
        )

    ALLOWED_UPDATE_FIELDS = {"display_name", "timezone"}
    updates = {
        k: v
        for k, v in request.model_dump().items()
        if v is not None and k in ALLOWED_UPDATE_FIELDS
    }
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        params = list(updates.values()) + [str(user_id)]

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE users SET {set_clause} WHERE id = %s RETURNING id, email, display_name, timezone",
                    tuple(params),
                )
                updated = cur.fetchone()

        if not updated:
            raise HTTPException(status_code=404, detail="User not found")

        return {"status": "success", "data": serialize_row(updated)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")
