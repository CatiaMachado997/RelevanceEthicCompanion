"""Sprint B Task 8 — `/api/connectors` REST surface.

Three endpoints power the Settings → Integrations page:
  * `GET    /api/connectors`                       — list status per connector
  * `POST   /api/connectors/{source_type}/backfill` — kick off a historical sync
  * `DELETE /api/connectors/{source_type}`         — disconnect + wipe state

OAuth callback paths still live in `routes/data_sources.py`; this router only
covers the operator surfaces added in Sprint B.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.data_ingestion import DataIngestionService
from services.context_manager import ContextManager
from services.embedding_service import EmbeddingService
from utils.db import get_db_connection
from utils.weaviate_client import get_weaviate_client
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from config import settings

logger = logging.getLogger(__name__)

# NOTE: router does NOT carry a prefix — main.py sets the prefix when including.
router = APIRouter(tags=["connectors"])

SUPPORTED = ["gmail", "slack", "google_calendar"]


class BackfillRequest(BaseModel):
    since: Optional[str] = None  # ISO-8601


def get_data_ingestion() -> DataIngestionService:
    """Build a DataIngestionService with the production wiring.

    Exposed as a FastAPI dependency so tests can override it with a mock.
    """
    weaviate_client = get_weaviate_client()
    embedding_service = EmbeddingService(settings.GEMINI_API_KEY)
    context_manager = ContextManager(
        weaviate_client=weaviate_client, embedding_service=embedding_service
    )
    return DataIngestionService(context_manager)


@router.get("")
async def list_connectors(
    user_id: str = Depends(get_current_read_user_id),
) -> Dict[str, Any]:
    """Return one row per supported connector."""
    rows = []
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for source_type in SUPPORTED:
                cur.execute(
                    """
                    SELECT oauth_token_encrypted, last_sync
                    FROM data_sources
                    WHERE user_id = %s AND source_type = %s
                    """,
                    (user_id, source_type),
                )
                ds = cur.fetchone()

                cur.execute(
                    """
                    SELECT MAX(item_at) AS last_item_at,
                           COUNT(*) AS items_count
                    FROM source_items
                    WHERE user_id = %s AND source_type = %s
                    """,
                    (user_id, source_type),
                )
                stats = cur.fetchone() or {}

                connected = bool(ds and ds.get("oauth_token_encrypted"))
                # Prefer item_at (when the item occurred); fall back to data_sources.last_sync.
                last_sync_at: Optional[datetime] = stats.get("last_item_at")
                if last_sync_at is None and ds:
                    last_sync_at = ds.get("last_sync")

                rows.append(
                    {
                        "source_type": source_type,
                        "connected": connected,
                        "last_sync_at": (
                            last_sync_at.isoformat() if last_sync_at else None
                        ),
                        "items_count": int(stats.get("items_count") or 0),
                    }
                )
    return {"connectors": rows}


@router.post("/{source_type}/backfill")
async def trigger_backfill(
    source_type: str,
    body: Optional[BackfillRequest] = None,
    user_id: str = Depends(get_current_user_id),
    ingestion: DataIngestionService = Depends(get_data_ingestion),
) -> Dict[str, Any]:
    """Kick off a historical sync for `source_type`.

    Trade-off: we await `start_backfill` directly rather than dispatching to a
    background task. Gmail / Slack syncs against reasonable windows complete in
    seconds, and the synchronous path keeps the response shape simple ("we
    have a job_id and a final status"). If sync windows ever grow past
    request-timeout territory, swap this for `BackgroundTasks` + a status
    polling endpoint.
    """
    if source_type not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"unsupported source: {source_type}")

    since_dt: Optional[datetime] = None
    if body and body.since:
        try:
            since_dt = datetime.fromisoformat(body.since.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"invalid since: {e}")

    try:
        job_id = await ingestion.start_backfill(user_id, source_type, since=since_dt)
        return {"job_id": str(job_id), "status": "complete"}
    except Exception as e:
        logger.error(f"❌ backfill failed for {source_type}: {e}")
        # start_backfill records the failure in connector_backfill_jobs before
        # re-raising; we surface the failure to the caller without leaking the
        # raw exception text in production. The job_id is unrecoverable here
        # because start_backfill only returns it on success.
        return {"job_id": "", "status": "failed"}


@router.delete("/{source_type}")
async def disconnect(
    source_type: str,
    user_id: str = Depends(get_current_user_id),
    ingestion: DataIngestionService = Depends(get_data_ingestion),
) -> Dict[str, Any]:
    """Disconnect a connector. Wipes vectors, source_items, and tokens."""
    if source_type not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"unsupported source: {source_type}")
    return await ingestion.disconnect_data_source(user_id, source_type)
