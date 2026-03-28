"""
Data Sources API Routes

Endpoints for connecting external data sources (Google Calendar, etc.)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from typing import Dict, Any, List, Optional
from datetime import datetime, UTC
import logging

from services.data_ingestion import DataIngestionService
from services.context_manager import ContextManager
from services.embedding_service import EmbeddingService
from utils.weaviate_client import get_weaviate_client
from utils.oauth_state import create_signed_state, validate_signed_state
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-sources", tags=["data-sources"])


# Dependency injection for data ingestion service
def get_data_ingestion() -> DataIngestionService:
    """Get or create data ingestion service instance"""
    weaviate_client = get_weaviate_client()
    embedding_service = EmbeddingService(settings.GEMINI_API_KEY)
    context_manager = ContextManager(
        weaviate_client=weaviate_client,
        embedding_service=embedding_service
    )
    return DataIngestionService(context_manager)


@router.get("/oauth/{source_type}/authorize")
async def start_oauth(
    source_type: str,
    user_id: str = Depends(get_current_user_id),
    ingestion: DataIngestionService = Depends(get_data_ingestion)
) -> Dict[str, str]:
    """
    Start OAuth authorization flow for a data source

    Args:
        source_type: Type of source ('google_calendar', etc.)
        user_id: Current user ID (from auth)

    Returns:
        Dict with authorization_url to redirect user to

    Example:
        GET /api/data-sources/oauth/google_calendar/authorize

        Response:
        {
            "authorization_url": "https://accounts.google.com/o/oauth2/auth?..."
        }
    """
    try:
        oauth_state = create_signed_state(user_id=user_id, source_type=source_type)
        auth_url = await ingestion.initiate_oauth(user_id, source_type, oauth_state=oauth_state)

        return {
            "authorization_url": auth_url,
            "source_type": source_type,
            "state": oauth_state
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start OAuth: {e}")
        raise HTTPException(status_code=500, detail="Failed to start authorization")


@router.get("/oauth/{source_type}/callback")
async def oauth_callback(
    source_type: str,
    code: Optional[str] = Query(None, description="Authorization code from OAuth provider"),
    state: Optional[str] = Query(None, description="User ID passed in state parameter"),
    error: Optional[str] = Query(None, description="Error code if user denied access"),
    ingestion: DataIngestionService = Depends(get_data_ingestion)
):
    """
    Handle OAuth callback from authorization provider.
    When the user denies access, the provider sends ?error=access_denied instead of ?code=xxx.

    Redirects to:
        /dashboard/integrations?connected={source_type}  on success
        /dashboard/integrations?error={source_type}_{reason}  on failure/denial
    """
    # User denied or provider returned an error
    if error or not code:
        reason = error or "denied"
        logger.info(f"OAuth denied for {source_type}: {reason}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={source_type}_{reason}",
            status_code=302
        )

    try:
        user_id = validate_signed_state(state=state, expected_source_type=source_type)
        result = await ingestion.handle_oauth_callback(
            source_type=source_type,
            authorization_code=code,
            user_id=user_id
        )
        if not result["success"]:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={source_type}_failed",
                status_code=302
            )
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?connected={source_type}",
            status_code=302
        )
    except HTTPException:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error=auth_failed",
            status_code=302
        )
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}", exc_info=True)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error=server_error",
            status_code=302
        )


@router.post("/sync/{source_type}")
async def trigger_manual_sync(
    source_type: str,
    user_id: str = Depends(get_current_user_id),
    ingestion: DataIngestionService = Depends(get_data_ingestion)
) -> Dict[str, Any]:
    """
    Manually trigger sync for a data source

    Args:
        source_type: Type of source ('google_calendar', etc.)
        user_id: Current user ID (from auth)

    Returns:
        Dict with sync results

    Example:
        POST /api/data-sources/sync/google_calendar

        Response:
        {
            "success": true,
            "message": "Synced 15 items from google_calendar",
            "items_synced": 15,
            "source_type": "google_calendar"
        }
    """
    try:
        result = await ingestion.sync_data_source(user_id, source_type)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sync failed")


@router.get("/connected")
async def get_connected_sources(
    user_id: str = Depends(get_current_read_user_id),
    ingestion: DataIngestionService = Depends(get_data_ingestion)
) -> List[Dict[str, Any]]:
    """
    Get list of connected data sources for current user

    Args:
        user_id: Current user ID (from auth)

    Returns:
        List of connected sources with status

    Example:
        GET /api/data-sources/connected

        Response:
        [
            {
                "source_type": "google_calendar",
                "enabled": true,
                "last_sync": "2026-02-06T10:30:00Z",
                "token_expires_at": "2026-02-13T10:00:00Z",
                "status": "connected"
            }
        ]
    """
    try:
        sources = await ingestion.get_connected_sources(user_id)
        return sources

    except Exception as e:
        logger.error(f"Failed to get connected sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sources")


@router.get("/stats")
async def get_source_stats(
    user_id: str = Depends(get_current_read_user_id),
    ingestion: DataIngestionService = Depends(get_data_ingestion),
) -> Dict[str, Any]:
    """
    Return item counts per connected source for the current user.

    Response:
        {
            "google_calendar": 15,
            "gmail": 42,
            "slack": 8,
            "total": 65
        }
    """
    try:
        return await ingestion.get_source_stats(user_id)
    except Exception as e:
        logger.error(f"Failed to get source stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")


@router.delete("/{source_type}")
async def disconnect_source(
    source_type: str,
    user_id: str = Depends(get_current_user_id),
    ingestion: DataIngestionService = Depends(get_data_ingestion)
) -> Dict[str, Any]:
    """
    Disconnect a data source (stop syncing)

    Args:
        source_type: Type of source to disconnect
        user_id: Current user ID (from auth)

    Returns:
        Dict with success status

    Example:
        DELETE /api/data-sources/google_calendar

        Response:
        {
            "success": true,
            "message": "google_calendar disconnected",
            "source_type": "google_calendar"
        }
    """
    try:
        success = await ingestion.disconnect_source(user_id, source_type)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to disconnect source")

        return {
            "success": True,
            "message": f"{source_type} disconnected",
            "source_type": source_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect source: {e}")
        raise HTTPException(status_code=500, detail="Failed to disconnect")


def _event_explanation(start_time, now: datetime) -> Optional[str]:
    """Generate a human-readable explanation for why an event is shown."""
    if not start_time:
        return None
    delta = start_time - now
    total_secs = delta.total_seconds()
    if total_secs < 0:
        return "Currently ongoing"
    if total_secs < 3600:
        mins = max(1, int(total_secs / 60))
        return f"Starts in {mins} minute{'s' if mins != 1 else ''}"
    hours = int(total_secs / 3600)
    if hours < 24:
        return f"Starts in {hours} hour{'s' if hours != 1 else ''}"
    days = int(hours / 24)
    return f"Coming up in {days} day{'s' if days != 1 else ''}"


@router.get("/events/upcoming")
async def get_upcoming_events(
    hours_ahead: int = Query(default=24, ge=1, le=168),
    user_id: str = Depends(get_current_read_user_id),
) -> Dict[str, Any]:
    """Get upcoming calendar events for the authenticated user."""
    try:
        weaviate_client = get_weaviate_client()
        embedding_service = EmbeddingService(settings.GEMINI_API_KEY)
        context_manager = ContextManager(
            weaviate_client=weaviate_client,
            embedding_service=embedding_service,
        )
        events = await context_manager.get_upcoming_events(str(user_id), hours_ahead=hours_ahead)
        now = datetime.now(UTC)
        return {
            "status": "success",
            "events": [
                {
                    "id": str(e.id),
                    "title": e.title,
                    "start_time": e.start_time.isoformat() if e.start_time else None,
                    "end_time": e.end_time.isoformat() if e.end_time else None,
                    "description": e.description,
                    "source": e.source,
                    "explanation": _event_explanation(e.start_time, now),
                }
                for e in events
            ],
        }
    except Exception as e:
        logger.error(f"Failed to fetch upcoming events: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch events")


@router.get("/health")
async def data_sources_health() -> Dict[str, str]:
    """
    Health check for data sources service

    Returns:
        Dict with health status
    """
    return {
        "status": "healthy",
        "service": "data_sources",
        "supported_sources": ["google_calendar"]
    }
