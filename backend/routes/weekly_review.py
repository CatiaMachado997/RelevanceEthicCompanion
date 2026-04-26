"""Sprint D Task 6 — `/api/weekly-review` route.

Single GET endpoint that returns the user's weekly review aggregation.
The router does NOT carry a prefix — main.py sets it when including.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from services.work_rollups import WorkRollupsService
from utils.supabase_auth import get_current_read_user_id

logger = logging.getLogger(__name__)

# NOTE: router does NOT carry a prefix — main.py sets the prefix when including.
router = APIRouter(tags=["weekly-review"])


def get_work_rollups_service() -> WorkRollupsService:
    return WorkRollupsService()


@router.get("", response_model=Dict[str, Any])
async def get_weekly_review(
    week_start: Optional[str] = None,
    user_id: str = Depends(get_current_read_user_id),
    rollups: WorkRollupsService = Depends(get_work_rollups_service),
) -> Dict[str, Any]:
    """Return the weekly review aggregation for ``user_id``.

    ``week_start`` is an optional ISO date (YYYY-MM-DD). When omitted, the
    service defaults to the most recent Monday (UTC).
    """
    parsed: Optional[date] = None
    if week_start is not None:
        try:
            parsed = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid week_start: {week_start!r} (expected YYYY-MM-DD)",
            )

    try:
        return rollups.get_weekly_review(user_id, week_start=parsed)
    except Exception as e:
        logger.error(f"Failed to build weekly review: {e}")
        raise HTTPException(status_code=500, detail="Failed to build weekly review")
