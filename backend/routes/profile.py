"""Profile API Routes"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel

from utils.db import get_db
from utils.serialization import serialize_row
from utils.supabase_auth import get_current_user_id, get_current_read_user_id

router = APIRouter(prefix="/api/profile", tags=["Profile"])


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    timezone: Optional[str] = None


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
                values_count = (cur.fetchone() or {}).get("cnt", 0)

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM goals WHERE user_id = %s AND status = 'active'",
                    (str(user_id),),
                )
                goals_count = (cur.fetchone() or {}).get("cnt", 0)

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
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profile: {str(e)}")


@router.put("/", response_model=dict)
async def update_profile(
    request: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
):
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
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

        return serialize_row(updated)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")
