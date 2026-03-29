# backend/routes/context.py
"""Context snapshot API route."""
from fastapi import APIRouter, Depends
from typing import Any, Dict

from utils.supabase_auth import get_current_read_user_id
from services.context_snapshot import ContextSnapshotService

router = APIRouter(prefix="/api/context", tags=["Context"])


@router.get("/snapshot", response_model=Dict[str, Any])
async def get_snapshot(user_id: str = Depends(get_current_read_user_id)):
    """Return the user's current 360° context snapshot."""
    service = ContextSnapshotService()
    return service.compute(str(user_id))
