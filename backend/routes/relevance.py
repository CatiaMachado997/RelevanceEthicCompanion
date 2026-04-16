"""
Relevance API Routes

Trigger relevance scans to propose ESL-checked proactive actions
like event summaries for meetings starting soon.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from services.context_manager import ContextManager

# OrchestratorV2 imported lazily inside get_orchestrator() below
from services.relevance_engine import RelevanceEngine
from utils.supabase_auth import get_current_read_user_id


class ScanResponse(BaseModel):
    user_id: str
    window_minutes: int
    results: List[Dict[str, Any]]
    scanned_at: str


router = APIRouter(prefix="/api/relevance", tags=["Relevance"])


def get_engine() -> RelevanceEngine:
    cm = ContextManager()
    return RelevanceEngine(cm)


def get_orchestrator():
    from services.orchestrator_v2 import OrchestratorV2  # lazy import

    cm = ContextManager()
    return OrchestratorV2(cm)


@router.post("/scan", response_model=ScanResponse)
async def scan(
    user_id: str = Depends(get_current_read_user_id),
    window_minutes: int = 15,
    engine: RelevanceEngine = Depends(get_engine),
    orchestrator=Depends(get_orchestrator),
):
    """
    Trigger a relevance scan for events starting within the next `window_minutes`.

    This route is useful during development to simulate the background worker
    that will run periodically.
    """
    try:
        results = await engine.scan_upcoming_events(
            user_id=user_id,
            window_minutes=window_minutes,
            orchestrator=orchestrator,
        )
        return ScanResponse(
            user_id=str(user_id),
            window_minutes=window_minutes,
            results=results,
            scanned_at=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")
