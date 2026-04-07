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
from services.context_manager import ContextManager
from models.context import SemanticMemoryEntry
from utils.db import get_db_connection
from config import settings

logger = logging.getLogger(__name__)

SUPPORTED_SOURCES = ["google_calendar", "gmail", "slack"]


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

            return {"success": True, "message": f"{source_type} connected", "source_type": source_type}
        except Exception as e:
            logger.error(f"❌ OAuth callback failed: {e}")
            return {"success": False, "message": str(e), "source_type": source_type}

    # ── Sync ───────────────────────────────────────────────────────────────

    async def sync_data_source(self, user_id: str, source_type: str) -> Dict[str, Any]:
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
            )

            items_synced = 0
            for raw in raw_items:
                try:
                    source_item = connector.normalize_to_source_item(raw, user_id)
                    await self._store_normalized_item(source_item)
                    await self._maybe_embed(source_item, user_id)
                    items_synced += 1
                except Exception as item_err:
                    logger.warning(f"⚠️ Failed to process item from {source_type}: {item_err}")

            await self._update_last_sync(user_id, source_type)
            await self._clear_sync_error(user_id, source_type)

            logger.info(f"✅ Sync complete: {items_synced} items from {source_type}")
            return {
                "success": True,
                "message": f"Synced {items_synced} items from {source_type}",
                "items_synced": items_synced,
                "source_type": source_type,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Sync failed for {source_type}: {error_msg}", exc_info=True)
            await self._record_sync_error(user_id, source_type, error_msg)
            return {
                "success": False,
                "message": f"Sync failed: {error_msg}",
                "items_synced": 0,
                "source_type": source_type,
            }

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
        """Store in M2 (Weaviate) if available — best-effort."""
        if not (self.context_manager.weaviate and self.context_manager.embedding_service):
            return
        try:
            content = f"{item.title}. {item.body or ''}"
            memory_entry = SemanticMemoryEntry(
                user_id=user_id,
                content=content,
                source=item.source_type,
                timestamp=datetime.now(timezone.utc),
                metadata={"external_id": item.external_id, **item.metadata},
            )
            await self.context_manager.store_semantic_memory(memory_entry)
        except Exception as e:
            logger.warning(f"⚠️ M2 embed failed for {item.external_id}: {e}")

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
                expires_aware = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
            else:
                expires_aware = datetime.fromisoformat(str(expires_at)).replace(tzinfo=timezone.utc)
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
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE data_sources
                    SET enabled = FALSE,
                        sync_error_message = 'Token expired — reconnect required'
                    WHERE user_id = %s AND source_type = %s
                    """,
                    (user_id, source_type),
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
                sources = []
                for row in cur.fetchall():
                    sources.append(
                        {
                            "source_type": row["source_type"],
                            "enabled": row["enabled"],
                            "last_sync": row["last_sync"].isoformat() if row["last_sync"] else None,
                            "token_expires_at": (
                                row["token_expires_at"].isoformat()
                                if row["token_expires_at"]
                                else None
                            ),
                            "status": "connected" if row["enabled"] else "disconnected",
                            "item_count": row["item_count"],
                            "sync_error": row["sync_error_message"],
                            "sync_error_count": row["sync_error_count"],
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
                counts = {row["source_type"]: row["item_count"] for row in cur.fetchall()}
        return {
            "google_calendar": counts.get("google_calendar", 0),
            "gmail": counts.get("gmail", 0),
            "slack": counts.get("slack", 0),
            "total": sum(counts.values()),
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
