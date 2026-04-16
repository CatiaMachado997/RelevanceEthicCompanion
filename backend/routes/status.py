"""User status endpoint — PUT/GET /api/status/ (not ESL-gated, user controls own mode)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
from utils.supabase_auth import get_current_user_id
from utils.db import get_db

router = APIRouter(prefix="/api/status", tags=["Status"])

STATUS_VALUES = Literal["available", "focus", "do_not_disturb", "away"]


class StatusUpdate(BaseModel):
    status: STATUS_VALUES
    status_until: Optional[datetime] = None


@router.put("/")
async def update_status(
    body: StatusUpdate, user_id: str = Depends(get_current_user_id)
):
    """Update user status. Not ESL-gated — user directly controls their own mode."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_settings (user_id, status, status_until)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE
                   SET status = EXCLUDED.status,
                       status_until = EXCLUDED.status_until,
                       updated_at = NOW()""",
                (user_id, body.status, body.status_until),
            )
    return {"status": body.status, "status_until": body.status_until}


@router.get("/")
async def get_status(user_id: str = Depends(get_current_user_id)):
    """Get current user status."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, status_until FROM user_settings WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"status": "available", "status_until": None}
    # dict_row factory returns dicts
    return {"status": row["status"], "status_until": row["status_until"]}
