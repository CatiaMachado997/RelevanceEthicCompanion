# backend/routes/context.py
"""Context snapshot API route."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict

from utils.supabase_auth import get_current_read_user_id
from services.context_snapshot import ContextSnapshotService

router = APIRouter(prefix="/api/context", tags=["Context"])
logger = logging.getLogger(__name__)


@router.get("/snapshot", response_model=Dict[str, Any])
async def get_snapshot(user_id: str = Depends(get_current_read_user_id)):
    """Return the user's current 360° context snapshot."""
    try:
        service = ContextSnapshotService()
        return service.compute(str(user_id))
    except Exception as e:
        logger.error(f"Context snapshot failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching context snapshot: {str(e)}")
