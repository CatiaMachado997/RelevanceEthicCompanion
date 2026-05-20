"""
Data Ingestion Service (Sprint 2)

Orchestrates data ingestion from external sources using the connector framework.
Each source maps to a BaseConnector; this service drives OAuth, sync, M1 storage,
M2 embedding, and error tracking.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from services.connectors import get_connector
from services.connectors.base import SourceItem
from services.connector_indexer import ConnectorIndexer
from services.context_manager import ContextManager
from utils.db import get_db_connection
from utils.weaviate_client import get_weaviate_client
from config import settings

logger = logging.getLogger(__name__)

SUPPORTED_SOURCES = ["google_calendar", "gmail", "slack"]

# Sentinel substring written by _mark_token_expired and read by _derive_status
_RECONNECT_SENTINEL = "reconnect required"


class TokenExpiredError(Exception):
    """Raised when an OAuth token has expired and cannot be refreshed."""

    def __init__(self, source_type: str):
        self.source_type = source_type
        super().__init__(f"Token expired for {source_type} — reconnect required")


class DataIngestionService:
    """
    Thin orchestrator: delegates auth + fetch + normalize to connectors;
    drives storage in M1 (source_items) and M2.
    """

    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        logger.info("✅ DataIngestionService initialized")

    # ── OAuth ──────────────────────────────────────────────────────────────

    async def initiate_oauth(
        self, user_id: str, source_type: str, oauth_state: Optional[str] = None
    ) -> str:
        connector = get_connector(source_type)
        url = connector.get_authorization_url(user_id, state=oauth_state)
        logger.info(f"✅ OAuth URL generated for {source_type}, user {user_id}")
        return url

    async def handle_oauth_callback(
        self, source_type: str, authorization_code: str, user_id: str
    ) -> Dict[str, Any]:
        try:
            connector = get_connector(source_type)
            tokens = connector.exchange_code_for_tokens(authorization_code)

            await self._store_data_source(
                user_id=user_id,
                source_type=source_type,
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                expires_at=tokens.get("expires_at"),
            )
            logger.info(f"✅ OAuth completed for {source_type}, user {user_id}")

            try:
                await self.sync_data_source(user_id, source_type)
            except Exception as sync_err:
                logger.warning(
                    f"⚠️ Initial sync failed for {source_type} (tokens stored): {sync_err}"
                )

            return {
                "success": True,
                "message": f"{source_type} connected",
                "source_type": source_type,
            }
        except Exception as e:
            logger.error(f"❌ OAuth callback failed: {e}")
            return {"success": False, "message": str(e), "source_type": source_type}

    # ── Sync ───────────────────────────────────────────────────────────────

    async def sync_data_source(
        self,
        user_id: str,
        source_type: str,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        logger.info(f"🔄 Starting sync: {source_type} for user {user_id}")

        try:
            access_token = await self._get_valid_token(user_id, source_type)
        except TokenExpiredError:
            raise  # route layer handles this

        try:
            connector = get_connector(source_type)
            raw_items = await connector.fetch_raw_items(
                access_token=access_token,
                refresh_token=None,  # token is already fresh
                since=since,
            )

            items_synced = 0
            for raw in raw_items:
                try:
                    source_item = connector.normalize_to_source_item(raw, user_id)
                    await self._store_normalized_item(source_item)
                    await self._maybe_embed(source_item, user_id)
                    items_synced += 1
                except Exception as item_err:
                    logger.warning(
                        f"⚠️ Failed to process item from {source_type}: {item_err}"
                    )

            await self._update_last_sync(user_id, source_type)
            await self._clear_sync_error(user_id, source_type)

            try:
                recent = await self._get_recent_synced_items(
                    user_id, source_type, limit=3
                )
            except Exception:
                logger.warning(
                    f"⚠️  Could not fetch recent items after sync for {source_type}"
                )
                recent = []
            logger.info(f"✅ Sync complete: {items_synced} items from {source_type}")
            return {
                "success": True,
                "message": f"Synced {items_synced} items",
                "items_synced": items_synced,
                "source_type": source_type,
                "recent": recent,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"❌ Sync failed for {source_type}: {error_msg}", exc_info=True
            )
            await self._record_sync_error(user_id, source_type, error_msg)
            return {
                "success": False,
                "message": f"Sync failed: {error_msg}",
                "items_synced": 0,
                "source_type": source_type,
            }

    # ── Backfill ───────────────────────────────────────────────────────────

    async def start_backfill(
        self,
        user_id: str,
        source_type: str,
        since: Optional[datetime] = None,
    ) -> str:
        """Run a backfill sync, tracking lifecycle in connector_backfill_jobs.

        Inserts a 'pending' row, transitions to 'running', invokes
        sync_data_source(since=since), and finalizes to 'complete' or
        'failed'. Re-raises on failure so callers can surface errors.
        Returns the backfill job id (UUID string).
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO connector_backfill_jobs
                        (user_id, source_type, status)
                    VALUES (%s, %s, 'pending')
                    RETURNING id
                    """,
                    (user_id, source_type),
                )
                job_id = str(cur.fetchone()["id"])
            conn.commit()

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE connector_backfill_jobs
                    SET status = 'running', started_at = NOW()
                    WHERE id = %s
                    """,
                    (job_id,),
                )
            conn.commit()

        try:
            result = await self.sync_data_source(user_id, source_type, since=since)
            items_processed = (
                result.get("items_synced", 0) if isinstance(result, dict) else 0
            )
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE connector_backfill_jobs
                        SET status = 'complete',
                            finished_at = NOW(),
                            items_processed = %s
                        WHERE id = %s
                        """,
                        (items_processed, job_id),
                    )
                conn.commit()
            return job_id
        except Exception as e:
            error_msg = str(e)[:500]
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE connector_backfill_jobs
                        SET status = 'failed',
                            finished_at = NOW(),
                            error_message = %s
                        WHERE id = %s
                        """,
                        (error_msg, job_id),
                    )
                conn.commit()
            raise

    # ── Storage helpers ────────────────────────────────────────────────────

    async def _store_normalized_item(self, item: SourceItem):
        """Upsert a normalized item into source_items (M1)."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO source_items
                        (user_id, source_type, source_item_type, external_id,
                         title, body, metadata, item_at, embedding_status, sensitivity)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, source_type, external_id)
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        body = EXCLUDED.body,
                        item_at = EXCLUDED.item_at,
                        metadata = EXCLUDED.metadata,
                        synced_at = NOW()
                    """,
                    (
                        item.user_id,
                        item.source_type,
                        item.source_item_type,
                        item.external_id,
                        item.title,
                        item.body,
                        json.dumps(item.metadata),
                        item.item_at,
                        item.embedding_status,
                        item.sensitivity,
                    ),
                )
            conn.commit()

    async def _maybe_embed(self, item: SourceItem, user_id: str):
        """Index the item into DocumentMemory via ConnectorIndexer.

        After Sprint B this is the only path connector content takes into
        Weaviate — `store_semantic_memory` is no longer called for source
        items because we want them to be cited by `search_documents` in chat.
        Best-effort: failures log and continue (Weaviate may be offline).
        """
        try:
            indexer = ConnectorIndexer()
            n = await indexer.index(item)
            logger.debug(f"indexed {n} chunk(s) for {item.source_type}:{item.external_id}")
            # Sprint F Task 1: record success on the row so the connectors
            # panel can show indexed counts. Failure path is owned by
            # ConnectorIndexer (it writes 'failed' + error before raising).
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """UPDATE source_items
                                  SET embedding_status = 'indexed',
                                      embedding_error = NULL
                                WHERE user_id = %s
                                  AND source_type = %s
                                  AND external_id = %s""",
                            (item.user_id, item.source_type, item.external_id),
                        )
                    conn.commit()
            except Exception as db_exc:
                logger.warning(
                    f"⚠️ embedding_status=indexed update failed for {item.external_id}: {db_exc}"
                )
        except Exception as e:
            logger.warning(f"⚠️ ConnectorIndexer failed for {item.external_id}: {e}")

    async def _store_data_source(
        self,
        user_id: str,
        source_type: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: Optional[str],
    ):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM data_sources WHERE user_id = %s AND source_type = %s",
                    (user_id, source_type),
                )
                existing = cur.fetchone()

                if existing:
                    cur.execute(
                        """
                        UPDATE data_sources
                        SET oauth_token_encrypted = %s,
                            oauth_refresh_token_encrypted = %s,
                            token_expires_at = %s,
                            enabled = TRUE,
                            last_sync = NULL,
                            sync_error_message = NULL,
                            sync_error_count = 0
                        WHERE user_id = %s AND source_type = %s
                        """,
                        (access_token, refresh_token, expires_at, user_id, source_type),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO data_sources
                            (user_id, source_type, oauth_token_encrypted,
                             oauth_refresh_token_encrypted, token_expires_at, enabled)
                        VALUES (%s, %s, %s, %s, %s, TRUE)
                        """,
                        (user_id, source_type, access_token, refresh_token, expires_at),
                    )
            conn.commit()

    async def _get_data_source_tokens(
        self, user_id: str, source_type: str
    ) -> Optional[Dict[str, str]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT oauth_token_encrypted, oauth_refresh_token_encrypted, token_expires_at
                    FROM data_sources
                    WHERE user_id = %s AND source_type = %s AND enabled = TRUE
                    """,
                    (user_id, source_type),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "access_token": row["oauth_token_encrypted"],
                    "refresh_token": row["oauth_refresh_token_encrypted"],
                    "expires_at": row["token_expires_at"],
                }

    async def _get_valid_token(self, user_id: str, source_type: str) -> str:
        """
        Return a valid access token, refreshing if it expires within 5 minutes.
        Persists new token to DB on refresh. Raises TokenExpiredError if refresh fails.
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT oauth_token_encrypted, oauth_refresh_token_encrypted, token_expires_at
                    FROM data_sources
                    WHERE user_id = %s AND source_type = %s AND enabled = TRUE
                    """,
                    (user_id, source_type),
                )
                row = cur.fetchone()

        if not row:
            raise TokenExpiredError(source_type)

        access_token = row["oauth_token_encrypted"]
        refresh_token = row["oauth_refresh_token_encrypted"]
        expires_at = row["token_expires_at"]

        # Normalise expires_at to an aware datetime
        if expires_at is not None:
            if hasattr(expires_at, "tzinfo"):
                expires_aware = (
                    expires_at
                    if expires_at.tzinfo
                    else expires_at.replace(tzinfo=timezone.utc)
                )
            else:
                expires_aware = datetime.fromisoformat(str(expires_at)).replace(
                    tzinfo=timezone.utc
                )
        else:
            expires_aware = None

        now = datetime.now(timezone.utc)
        if expires_aware and expires_aware > now + timedelta(minutes=5):
            return access_token  # Still valid

        # Token expired — try to refresh
        if not refresh_token:
            await self._mark_token_expired(user_id, source_type)
            raise TokenExpiredError(source_type)

        try:
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
                client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            )
            creds.refresh(Request())
            new_expires_at = now + timedelta(seconds=3600)  # Google default: 1h
            if creds.expiry:
                new_expires_at = datetime.fromtimestamp(
                    creds.expiry.timestamp(), tz=timezone.utc
                )
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE data_sources
                        SET oauth_token_encrypted = %s, token_expires_at = %s
                        WHERE user_id = %s AND source_type = %s
                        """,
                        (creds.token, new_expires_at, user_id, source_type),
                    )
            logger.info(f"✅ Token refreshed for {source_type}, user {user_id}")
            return creds.token
        except Exception as e:
            logger.warning(f"⚠️  Token refresh failed for {source_type}: {e}")
            await self._mark_token_expired(user_id, source_type)
            raise TokenExpiredError(source_type)

    async def _mark_token_expired(self, user_id: str, source_type: str):
        """Disable source and record reconnect-required error."""
        error_msg = f"Token expired — {_RECONNECT_SENTINEL}"
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE data_sources
                    SET enabled = FALSE,
                        sync_error_message = %s
                    WHERE user_id = %s AND source_type = %s
                    """,
                    (error_msg, user_id, source_type),
                )

    async def _update_last_sync(self, user_id: str, source_type: str):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE data_sources SET last_sync = %s WHERE user_id = %s AND source_type = %s",
                    (datetime.now(timezone.utc), user_id, source_type),
                )
            conn.commit()

    async def _record_sync_error(self, user_id: str, source_type: str, message: str):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE data_sources
                    SET sync_error_message = %s,
                        sync_error_count = COALESCE(sync_error_count, 0) + 1
                    WHERE user_id = %s AND source_type = %s
                    """,
                    (message[:500], user_id, source_type),
                )
            conn.commit()

    async def _clear_sync_error(self, user_id: str, source_type: str):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE data_sources
                    SET sync_error_message = NULL, sync_error_count = 0
                    WHERE user_id = %s AND source_type = %s
                    """,
                    (user_id, source_type),
                )
            conn.commit()

    async def _get_recent_synced_items(
        self, user_id: str, source_type: str, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Return the most-recent source items for display in sync responses and the connected list."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT title, item_at
                    FROM source_items
                    WHERE user_id = %s AND source_type = %s
                    ORDER BY item_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (user_id, source_type, limit),
                )
                rows = cur.fetchall()
        return [
            {
                "title": row["title"],
                "item_at": row["item_at"].isoformat() if row["item_at"] else None,
            }
            for row in rows
        ]

    def _derive_status(self, row: dict) -> str:
        """Derive display status from a data_sources row dict."""
        if not row["enabled"]:
            if row.get("sync_error_message") and _RECONNECT_SENTINEL in (
                row["sync_error_message"] or ""
            ):
                return "token_expired"
            return "disconnected"
        last_sync = row.get("last_sync")
        if last_sync is None:
            return "sync_needed"
        if not hasattr(last_sync, "tzinfo"):
            last_sync = datetime.fromisoformat(str(last_sync))
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)
        if last_sync < datetime.now(timezone.utc) - timedelta(hours=24):
            return "sync_needed"
        return "synced"

    # ── Query ──────────────────────────────────────────────────────────────

    async def get_connected_sources(self, user_id: str) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        ds.source_type,
                        ds.enabled,
                        ds.last_sync,
                        ds.token_expires_at,
                        ds.sync_error_message,
                        ds.sync_error_count,
                        COUNT(si.id) AS item_count
                    FROM data_sources ds
                    LEFT JOIN source_items si
                        ON si.user_id = ds.user_id AND si.source_type = ds.source_type
                    WHERE ds.user_id = %s
                    GROUP BY ds.source_type, ds.enabled, ds.last_sync,
                             ds.token_expires_at, ds.sync_error_message, ds.sync_error_count
                    ORDER BY ds.source_type
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()

        sources = []
        for row in rows:
            recent_items = await self._get_recent_synced_items(
                user_id, row["source_type"]
            )
            sources.append(
                {
                    "source_type": row["source_type"],
                    "enabled": row["enabled"],
                    "last_sync": (
                        row["last_sync"].isoformat() if row["last_sync"] else None
                    ),
                    "token_expires_at": (
                        row["token_expires_at"].isoformat()
                        if row["token_expires_at"]
                        else None
                    ),
                    "status": self._derive_status(row),
                    "item_count": row["item_count"],
                    "sync_error": row["sync_error_message"],
                    "sync_error_count": row["sync_error_count"],
                    "recent_items": recent_items,
                }
            )
        return sources

    async def get_source_stats(self, user_id: str) -> Dict[str, Any]:
        """Return item counts per source for the stats endpoint."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_type, COUNT(*) AS item_count
                    FROM source_items
                    WHERE user_id = %s
                    GROUP BY source_type
                    """,
                    (user_id,),
                )
                counts = {
                    row["source_type"]: row["item_count"] for row in cur.fetchall()
                }
        return {
            "google_calendar": counts.get("google_calendar", 0),
            "gmail": counts.get("gmail", 0),
            "slack": counts.get("slack", 0),
            "total": sum(counts.values()),
        }

    async def disconnect_data_source(
        self, user_id: str, source_type: str
    ) -> Dict[str, Any]:
        """Disconnect a connector and wipe everything associated with it.

        Order matters:
          1. Weaviate vectors (DocumentMemory matching user_id + source_type)
          2. Postgres source_items rows
          3. Postgres data_sources row (tokens + state)

        Vectors are deleted first so that if the SQL DELETE fails the user
        can retry — SQL still tells us there's cleanup to do. Conversely if
        SQL is wiped first and vector deletion fails, we'd have orphan
        vectors with no token to drive a retry from.

        Returns a dict with counts:
            {"vectors_deleted": int, "items_deleted": int, "tokens_deleted": int}
        """
        # Step 1: vectors first
        vectors_deleted = 0
        weav = get_weaviate_client()
        if weav is not None:
            vectors_deleted = weav.delete_by_filter(
                "DocumentMemory",
                {"user_id": str(user_id), "source_type": source_type},
            )

        # Steps 2 & 3: SQL
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM source_items WHERE user_id = %s AND source_type = %s",
                    (user_id, source_type),
                )
                items_deleted = cur.rowcount or 0
                cur.execute(
                    "DELETE FROM data_sources WHERE user_id = %s AND source_type = %s",
                    (user_id, source_type),
                )
                tokens_deleted = cur.rowcount or 0
            conn.commit()

        logger.info(
            f"✅ disconnected {source_type} for {user_id}: "
            f"{vectors_deleted} vectors, {items_deleted} items, "
            f"{tokens_deleted} tokens"
        )
        return {
            "vectors_deleted": vectors_deleted,
            "items_deleted": items_deleted,
            "tokens_deleted": tokens_deleted,
        }

    async def disconnect_source(self, user_id: str, source_type: str) -> bool:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE data_sources SET enabled = FALSE WHERE user_id = %s AND source_type = %s",
                        (user_id, source_type),
                    )
                conn.commit()
            logger.info(f"✅ Disconnected {source_type} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to disconnect {source_type}: {e}")
            return False
