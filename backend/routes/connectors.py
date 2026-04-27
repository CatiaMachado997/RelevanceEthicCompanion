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
from services.connector_indexer import ConnectorIndexer
from services.connectors.base import SourceItem
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


def get_connector_indexer() -> ConnectorIndexer:
    """FastAPI dependency for ConnectorIndexer; tests override with a mock."""
    return ConnectorIndexer()


@router.post("/{source_type}/reindex")
async def reindex_source(
    source_type: str,
    user_id: str = Depends(get_current_user_id),
    indexer: ConnectorIndexer = Depends(get_connector_indexer),
) -> Dict[str, Any]:
    """Retry indexing for items where embedding_status != 'completed'.

    Pulls up to 200 stuck rows for `(user_id, source_type)`, calls
    `ConnectorIndexer.index()` directly on each (so per-item failures count
    rather than being silently swallowed by `_maybe_embed`), and on success
    flips the row to 'completed'.

    No ESL gate — this is operational/internal, matching the
    `tool_telemetry.record_tool_call` precedent.
    """
    if source_type not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"unsupported source: {source_type}")

    rows: list[dict] = []
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, source_type, source_item_type, external_id,
                       title, body, metadata, item_at, embedding_status, sensitivity
                FROM source_items
                WHERE user_id = %s
                  AND source_type = %s
                  AND (embedding_status IS NULL OR embedding_status != 'completed')
                LIMIT 200
                """,
                (user_id, source_type),
            )
            rows = list(cur.fetchall() or [])

    processed = 0
    succeeded = 0
    for row in rows:
        processed += 1
        try:
            metadata = row.get("metadata") or {}
            if isinstance(metadata, str):
                # Defensive: psycopg may return JSONB as text in some configs.
                import json as _json
                try:
                    metadata = _json.loads(metadata)
                except Exception:
                    metadata = {}
            item_at = row.get("item_at")
            item = SourceItem(
                user_id=str(row.get("user_id")),
                source_type=row.get("source_type"),
                source_item_type=row.get("source_item_type"),
                external_id=row.get("external_id"),
                title=row.get("title") or "",
                body=row.get("body"),
                metadata=metadata,
                item_at=item_at.isoformat() if hasattr(item_at, "isoformat") else item_at,
                embedding_status=row.get("embedding_status") or "pending",
                sensitivity=row.get("sensitivity") or 0,
            )
            await indexer.index(item)
            # Mirror data_ingestion._maybe_embed: mark completed + clear error.
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """UPDATE source_items
                                  SET embedding_status = 'completed',
                                      embedding_error = NULL
                                WHERE user_id = %s
                                  AND source_type = %s
                                  AND external_id = %s""",
                            (item.user_id, item.source_type, item.external_id),
                        )
                    conn.commit()
            except Exception as db_exc:
                logger.warning(f"⚠️ reindex completed-update failed for {item.external_id}: {db_exc}")
            succeeded += 1
        except Exception as e:
            # ConnectorIndexer already wrote 'failed' + embedding_error and
            # emitted telemetry before re-raising. Just keep the batch going.
            logger.info(f"reindex item failed ({source_type}/{row.get('external_id')}): {e}")

    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": processed - succeeded,
    }


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
