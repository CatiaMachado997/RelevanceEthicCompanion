"""
Data Ingestion Service

Orchestrates data ingestion from external sources (Google Calendar, etc.)
and stores in M1 (PostgreSQL) + M2 (Weaviate with embeddings).

This is 100% YOUR CUSTOM CODE - not provided by any framework.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from services.google_calendar_sync import GoogleCalendarSync
from services.gmail_sync import GmailSync
from services.slack_sync import SlackSync
from services.context_manager import ContextManager
from models.context import Event, SemanticMemoryEntry
from utils.db import get_db_connection

logger = logging.getLogger(__name__)


class DataIngestionService:
    """
    Coordinates data ingestion from external sources

    Responsibilities:
    - Manage OAuth flows for data sources
    - Fetch data from external APIs
    - Store in M1 (PostgreSQL) for structured queries
    - Generate embeddings and store in M2 (Weaviate) for semantic search
    - Track sync status and prevent duplicates
    """

    def __init__(self, context_manager: ContextManager):
        """
        Initialize data ingestion service

        Args:
            context_manager: For storing in M1 + M2
        """
        self.context_manager = context_manager

        # Initialize sync adapters
        self.google_calendar = GoogleCalendarSync()
        self.gmail = GmailSync()
        self.slack = SlackSync()

        logger.info("✅ DataIngestionService initialized")

    async def initiate_oauth(self, user_id: str, source_type: str, oauth_state: Optional[str] = None) -> str:
        """
        Start OAuth flow for a data source

        Args:
            user_id: User ID requesting authorization
            source_type: Type of source ('google_calendar', etc.)

        Returns:
            Authorization URL to redirect user to

        Raises:
            ValueError: If source_type is not supported
        """
        if source_type == 'google_calendar':
            auth_url = self.google_calendar.get_authorization_url(user_id, oauth_state=oauth_state)
            logger.info(f"✅ Generated OAuth URL for {source_type}, user {user_id}")
            return auth_url
        elif source_type == 'gmail':
            auth_url = self.gmail.get_authorization_url(user_id, oauth_state=oauth_state)
            logger.info(f"✅ Generated OAuth URL for {source_type}, user {user_id}")
            return auth_url
        elif source_type == 'slack':
            auth_url = self.slack.get_authorization_url(user_id, oauth_state=oauth_state)
            logger.info(f"✅ Generated OAuth URL for {source_type}, user {user_id}")
            return auth_url
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    async def handle_oauth_callback(
        self,
        source_type: str,
        authorization_code: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Handle OAuth callback and store tokens

        Args:
            source_type: Type of source ('google_calendar', etc.)
            authorization_code: Authorization code from OAuth provider
            user_id: User ID who authorized

        Returns:
            Dict with success status and message
        """
        try:
            if source_type == 'google_calendar':
                # Exchange code for tokens
                tokens = self.google_calendar.exchange_code_for_tokens(authorization_code)

                # Store tokens in database (encrypted in production!)
                await self._store_data_source(
                    user_id=user_id,
                    source_type=source_type,
                    access_token=tokens['access_token'],
                    refresh_token=tokens['refresh_token'],
                    expires_at=tokens['expires_at']
                )

                logger.info(f"✅ OAuth completed for {source_type}, user {user_id}")

                # Trigger initial sync
                await self.sync_data_source(user_id, source_type)

                return {
                    "success": True,
                    "message": f"{source_type} connected successfully",
                    "source_type": source_type
                }
            elif source_type == 'gmail':
                tokens = self.gmail.exchange_code_for_tokens(authorization_code)

                await self._store_data_source(
                    user_id=user_id,
                    source_type=source_type,
                    access_token=tokens['access_token'],
                    refresh_token=tokens['refresh_token'],
                    expires_at=tokens['expires_at']
                )

                logger.info(f"✅ OAuth completed for {source_type}, user {user_id}")

                # Trigger initial sync
                await self.sync_data_source(user_id, source_type)

                return {
                    "success": True,
                    "message": f"{source_type} connected successfully",
                    "source_type": source_type
                }
            elif source_type == 'slack':
                tokens = self.slack.exchange_code_for_tokens(authorization_code)

                await self._store_data_source(
                    user_id=user_id,
                    source_type=source_type,
                    access_token=tokens['access_token'],
                    refresh_token=tokens['refresh_token'],
                    expires_at=tokens['expires_at']
                )

                logger.info(f"✅ OAuth completed for {source_type}, user {user_id}")

                # Trigger initial sync
                await self.sync_data_source(user_id, source_type)

                return {
                    "success": True,
                    "message": f"{source_type} connected successfully",
                    "source_type": source_type
                }
            else:
                raise ValueError(f"Unsupported source type: {source_type}")

        except Exception as e:
            logger.error(f"❌ OAuth callback failed: {e}")
            return {
                "success": False,
                "message": f"Failed to connect {source_type}: {str(e)}",
                "source_type": source_type
            }

    async def _store_data_source(
        self,
        user_id: str,
        source_type: str,
        access_token: str,
        refresh_token: str,
        expires_at: str
    ):
        """
        Store data source credentials in database

        WARNING: In production, tokens MUST be encrypted!
        For MVP, we're storing in plain text. Use encryption before production.

        Args:
            user_id: User ID
            source_type: Source type
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_at: Token expiration time
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if source already exists
                cur.execute("""
                    SELECT id FROM data_sources
                    WHERE user_id = %s AND source_type = %s
                """, (user_id, source_type))

                existing = cur.fetchone()

                if existing:
                    # Update existing
                    cur.execute("""
                        UPDATE data_sources
                        SET oauth_token_encrypted = %s,
                            oauth_refresh_token_encrypted = %s,
                            token_expires_at = %s,
                            enabled = TRUE,
                            last_sync = NULL
                        WHERE user_id = %s AND source_type = %s
                    """, (access_token, refresh_token, expires_at, user_id, source_type))
                else:
                    # Insert new
                    cur.execute("""
                        INSERT INTO data_sources
                        (user_id, source_type, oauth_token_encrypted, oauth_refresh_token_encrypted, token_expires_at, enabled)
                        VALUES (%s, %s, %s, %s, %s, TRUE)
                    """, (user_id, source_type, access_token, refresh_token, expires_at))

                conn.commit()

        logger.info(f"✅ Stored credentials for {source_type}, user {user_id}")

    async def sync_data_source(self, user_id: str, source_type: str) -> Dict[str, Any]:
        """
        Sync data from external source to M1 + M2

        Flow:
        1. Retrieve OAuth tokens from database
        2. Fetch data from external API
        3. Normalize data to internal models
        4. Store in M1 (PostgreSQL) for structured queries
        5. Generate embeddings and store in M2 (Weaviate) for semantic search
        6. Update last_sync timestamp

        Args:
            user_id: User ID
            source_type: Source type ('google_calendar', etc.)

        Returns:
            Dict with sync results
        """
        try:
            logger.info(f"🔄 Starting sync: {source_type} for user {user_id}")

            # Step 1: Get OAuth tokens
            tokens = await self._get_data_source_tokens(user_id, source_type)
            if not tokens:
                return {
                    "success": False,
                    "message": f"{source_type} not connected",
                    "items_synced": 0
                }

            # Step 2: Fetch data from external API
            if source_type == 'google_calendar':
                items_synced = await self._sync_google_calendar(
                    user_id=user_id,
                    access_token=tokens['access_token'],
                    refresh_token=tokens['refresh_token']
                )
            elif source_type == 'gmail':
                items_synced = await self._sync_gmail(
                    user_id=user_id,
                    access_token=tokens['access_token'],
                    refresh_token=tokens['refresh_token']
                )
            elif source_type == 'slack':
                items_synced = await self._sync_slack(
                    user_id=user_id,
                    access_token=tokens['access_token']
                )
            else:
                raise ValueError(f"Unsupported source type: {source_type}")

            # Step 3: Update last_sync timestamp
            await self._update_last_sync(user_id, source_type)

            logger.info(f"✅ Sync complete: {items_synced} items from {source_type}")

            return {
                "success": True,
                "message": f"Synced {items_synced} items from {source_type}",
                "items_synced": items_synced,
                "source_type": source_type
            }

        except Exception as e:
            logger.error(f"❌ Sync failed for {source_type}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Sync failed: {str(e)}",
                "items_synced": 0,
                "source_type": source_type
            }

    async def _get_data_source_tokens(self, user_id: str, source_type: str) -> Optional[Dict[str, str]]:
        """Retrieve OAuth tokens from database"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT oauth_token_encrypted, oauth_refresh_token_encrypted, token_expires_at
                    FROM data_sources
                    WHERE user_id = %s AND source_type = %s AND enabled = TRUE
                """, (user_id, source_type))

                result = cur.fetchone()
                if not result:
                    return None

                return {
                    'access_token': result[0],
                    'refresh_token': result[1],
                    'expires_at': result[2]
                }

    async def _sync_google_calendar(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str
    ) -> int:
        """
        Sync Google Calendar events to M1 + M2

        Returns:
            Number of events synced
        """
        # Fetch events from Google Calendar
        google_events = await self.google_calendar.fetch_events(
            access_token=access_token,
            refresh_token=refresh_token
        )

        items_synced = 0

        for google_event in google_events:
            try:
                # Normalize to Event model
                event = self.google_calendar.normalize_event(google_event, user_id)

                # Store in M1 (PostgreSQL) - YOUR structured storage
                await self.context_manager.store_event(event)

                # Store in M2 (Weaviate) with embeddings - YOUR semantic search
                if self.context_manager.weaviate and self.context_manager.embedding_service:
                    # Generate embedding for event content
                    event_content = f"{event.title}. {event.description or ''}"

                    # Store as semantic memory
                    memory_entry = SemanticMemoryEntry(
                        user_id=user_id,
                        content=event_content,
                        source='google_calendar',
                        timestamp=event.start_time,
                        metadata={
                            'event_id': event.id,
                            'location': event.location,
                            'start_time': event.start_time.isoformat(),
                            'end_time': event.end_time.isoformat() if event.end_time else None
                        }
                    )

                    await self.context_manager.store_semantic_memory(memory_entry)

                items_synced += 1

            except Exception as e:
                logger.warning(f"⚠️  Failed to sync event {google_event.get('id')}: {e}")
                continue

        return items_synced

    async def _sync_gmail(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str
    ) -> int:
        """
        Sync Gmail messages to M2 (semantic memory)

        Returns:
            Number of messages synced
        """
        messages = self.gmail.fetch_messages(
            access_token=access_token,
            refresh_token=refresh_token
        )

        items_synced = 0

        for message in messages:
            try:
                if self.context_manager.weaviate and self.context_manager.embedding_service:
                    content = f"Email from {message['from']}: {message['subject']}. {message['snippet']}"

                    memory_entry = SemanticMemoryEntry(
                        user_id=user_id,
                        content=content,
                        source='gmail',
                        timestamp=datetime.now(timezone.utc),
                        metadata={
                            'message_id': message['id'],
                            'subject': message['subject'],
                            'from': message['from'],
                            'date': message['date'],
                        }
                    )

                    await self.context_manager.store_semantic_memory(memory_entry)

                items_synced += 1

            except Exception as e:
                logger.warning(f"⚠️  Failed to sync Gmail message {message.get('id')}: {e}")
                continue

        return items_synced

    async def _sync_slack(
        self,
        user_id: str,
        access_token: str
    ) -> int:
        """
        Sync Slack messages to M2 (semantic memory)

        Returns:
            Number of messages synced
        """
        messages = self.slack.fetch_messages(access_token=access_token)

        items_synced = 0

        for message in messages:
            try:
                if self.context_manager.weaviate and self.context_manager.embedding_service:
                    content = f"Slack #{message['channel']}: {message['text']}"

                    memory_entry = SemanticMemoryEntry(
                        user_id=user_id,
                        content=content,
                        source='slack',
                        timestamp=datetime.now(timezone.utc),
                        metadata={
                            'channel': message['channel'],
                            'ts': message['ts'],
                            'user': message['user'],
                        }
                    )

                    await self.context_manager.store_semantic_memory(memory_entry)

                items_synced += 1

            except Exception as e:
                logger.warning(f"⚠️  Failed to sync Slack message {message.get('ts')}: {e}")
                continue

        return items_synced

    async def _update_last_sync(self, user_id: str, source_type: str):
        """Update last_sync timestamp"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE data_sources
                    SET last_sync = %s
                    WHERE user_id = %s AND source_type = %s
                """, (datetime.now(timezone.utc), user_id, source_type))
                conn.commit()

    async def get_connected_sources(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get list of connected data sources for user

        Args:
            user_id: User ID

        Returns:
            List of connected sources with status
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source_type, enabled, last_sync, token_expires_at
                    FROM data_sources
                    WHERE user_id = %s
                    ORDER BY source_type
                """, (user_id,))

                sources = []
                for row in cur.fetchall():
                    sources.append({
                        'source_type': row['source_type'],
                        'enabled': row['enabled'],
                        'last_sync': row['last_sync'].isoformat() if row['last_sync'] else None,
                        'token_expires_at': row['token_expires_at'].isoformat() if row['token_expires_at'] else None,
                        'status': 'connected' if row['enabled'] else 'disconnected'
                    })

                return sources

    async def disconnect_source(self, user_id: str, source_type: str) -> bool:
        """
        Disconnect a data source (disable syncing)

        Args:
            user_id: User ID
            source_type: Source type to disconnect

        Returns:
            True if successful
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE data_sources
                        SET enabled = FALSE
                        WHERE user_id = %s AND source_type = %s
                    """, (user_id, source_type))
                    conn.commit()

            logger.info(f"✅ Disconnected {source_type} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to disconnect {source_type}: {e}")
            return False


# Example usage
if __name__ == "__main__":
    import asyncio
    from services.embedding_service import EmbeddingService
    from utils.weaviate_client import get_weaviate_client
    import os
    from dotenv import load_dotenv

    load_dotenv()

    async def test_data_ingestion():
        """Test data ingestion service"""

        # Initialize dependencies
        weaviate_client = get_weaviate_client()
        embedding_service = EmbeddingService(os.getenv('GEMINI_API_KEY'))

        context_manager = ContextManager(
            weaviate_client=weaviate_client,
            embedding_service=embedding_service
        )

        ingestion = DataIngestionService(context_manager)

        print("\n" + "=" * 60)
        print("DATA INGESTION SERVICE TEST")
        print("=" * 60)

        # Step 1: Get OAuth URL
        test_user_id = "test-user-123"
        auth_url = await ingestion.initiate_oauth(test_user_id, 'google_calendar')

        print(f"\n1. OAuth Authorization URL:")
        print(f"   {auth_url}")
        print(f"\n2. Open URL in browser and authorize")
        print(f"3. Copy 'code' parameter from redirect")
        print(f"4. Call handle_oauth_callback() with code")

    asyncio.run(test_data_ingestion())
