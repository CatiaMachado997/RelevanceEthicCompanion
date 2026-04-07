"""
Context Manager (V2 - PostgreSQL + Weaviate)

Manages user context using hybrid memory:
- M1 (PostgreSQL): Structured data (users, values, goals, events)
- M2 (Weaviate): Semantic memory (embeddings for conversations, events, goals)

THIS IS 100% YOUR ARCHITECTURE:
- How you combine M1 + M2
- What queries you run
- How you build context
- When you generate embeddings
"""

from typing import List, Dict, Any, Optional, Literal
from datetime import datetime, timedelta, timezone
import uuid
import logging
import json

from esl.models import UserValue, UserContext, ValueType
from models.context import Goal, Event, SemanticMemoryEntry, GoalStatus
from models.relevance import RelevanceContext
from utils.db import get_db_connection
from utils.weaviate_client import WeaviateClient, get_weaviate_client

logger = logging.getLogger(__name__)


class ContextManager:
    """
    V2 Context Manager - Hybrid Memory System

    YOUR INTELLIGENCE:
    - What to retrieve from M1 vs M2
    - How to combine structured + semantic data
    - What context to surface for decisions
    - When to generate embeddings
    """

    def __init__(
        self,
        weaviate_client: Optional[WeaviateClient] = None,
        embedding_service: Optional[Any] = None
    ):
        """
        Initialize context manager

        Args:
            weaviate_client: Weaviate client for M2 operations (auto-connects if None)
            embedding_service: Service for generating embeddings
        """
        if weaviate_client is None:
            try:
                weaviate_client = get_weaviate_client()
                logger.info("✅ Weaviate singleton connected")
            except Exception as e:
                logger.warning(f"⚠️  Weaviate auto-connect failed: {e} — semantic memory disabled")
                weaviate_client = None

        self.weaviate = weaviate_client
        self.embedding_service = embedding_service

        logger.info("✅ ContextManager initialized (PostgreSQL + Weaviate)")

    # ==================== M1: User Values (PostgreSQL) ====================

    async def get_user_values(self, user_id: str) -> List[UserValue]:
        """
        Retrieve all active user values from PostgreSQL

        YOUR QUERY LOGIC: What to fetch, how to sort
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, type, value, priority, active, metadata, created_at, updated_at
                    FROM user_values
                    WHERE user_id = %s AND active = TRUE
                    ORDER BY priority ASC
                """, (user_id,))

                rows = cur.fetchall()
                values = []

                for row in rows:
                    values.append(UserValue(
                        id=str(row['id']),
                        user_id=str(row['user_id']),
                        type=ValueType(row['type']),
                        value=row['value'],
                        priority=row['priority'],
                        active=row['active'],
                        metadata=row['metadata'] or {},
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    ))

                logger.debug(f"✅ Retrieved {len(values)} user values for {user_id}")
                return values

    async def create_user_value(self, user_value: UserValue) -> Optional[UserValue]:
        """Create a new user value in PostgreSQL"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                value_id = user_value.id or str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO user_values (id, user_id, type, value, priority, active, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, created_at
                """, (
                    value_id,
                    user_value.user_id,
                    user_value.type.value,
                    user_value.value,
                    user_value.priority,
                    user_value.active,
                    json.dumps(user_value.metadata)
                ))

                result = cur.fetchone()
                user_value.id = str(result[0])
                user_value.created_at = result[1]

                logger.debug(f"✅ Created user value: {user_value.id}")
                return user_value

    async def update_user_value(
        self, value_id: str, updates: Dict[str, Any]
    ) -> Optional[UserValue]:
        """Update a user value in PostgreSQL"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build dynamic UPDATE query
                set_clauses = []
                params = []

                for key, val in updates.items():
                    if key in ['type', 'value', 'priority', 'active', 'metadata']:
                        set_clauses.append(f"{key} = %s")
                        params.append(val)

                if not set_clauses:
                    return None

                params.append(value_id)
                query = f"UPDATE user_values SET {', '.join(set_clauses)}, updated_at = NOW() WHERE id = %s"

                cur.execute(query, params)

                if cur.rowcount > 0:
                    logger.debug(f"✅ Updated user value: {value_id}")
                    return await self.get_user_value_by_id(value_id)
                return None

    async def get_user_value_by_id(self, value_id: str) -> Optional[UserValue]:
        """Get a single user value by ID"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, type, value, priority, active, metadata, created_at, updated_at
                    FROM user_values
                    WHERE id = %s
                """, (value_id,))

                row = cur.fetchone()
                if row:
                    return UserValue(
                        id=str(row['id']),
                        user_id=str(row['user_id']),
                        type=ValueType(row['type']),
                        value=row['value'],
                        priority=row['priority'],
                        active=row['active'],
                        metadata=row['metadata'] or {},
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                return None

    async def delete_user_value(self, value_id: str) -> bool:
        """Delete a user value from PostgreSQL"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM user_values WHERE id = %s", (value_id,))
                deleted = cur.rowcount > 0

                if deleted:
                    logger.debug(f"✅ Deleted user value: {value_id}")
                return deleted

    # ==================== M1: Conversation History (PostgreSQL) ====================

    async def store_conversation_turn(
        self,
        user_id: str,
        role: Literal["user", "assistant"],
        content: str,
        conversation_id: str = None
    ) -> None:
        """Store a single conversation turn in PostgreSQL for reliable ordered retrieval."""
        if role not in ("user", "assistant"):
            raise ValueError(f"Invalid role: {role}. Must be 'user' or 'assistant'")

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if conversation_id:
                    cur.execute("""
                        INSERT INTO conversation_turns (user_id, role, content, conversation_id)
                        VALUES (%s, %s, %s, %s)
                    """, (user_id, role, content, conversation_id))
                else:
                    cur.execute("""
                        INSERT INTO conversation_turns (user_id, role, content)
                        VALUES (%s, %s, %s)
                    """, (user_id, role, content))
        logger.debug(f"Stored conversation turn ({role}) for user {user_id}")

    async def get_conversation_history(
        self,
        user_id: str,
        limit: int = 20,
        conversation_id: str = None
    ) -> List[Dict[str, str]]:
        """
        Retrieve the last N conversation turns in chronological order.
        Returns list of dicts with 'role' and 'content' keys.
        If conversation_id is provided, returns only turns for that conversation.
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if conversation_id:
                    cur.execute("""
                        SELECT role, content, created_at FROM conversation_turns
                        WHERE user_id = %s AND conversation_id = %s
                        ORDER BY created_at ASC LIMIT %s
                    """, (user_id, conversation_id, limit))
                else:
                    cur.execute("""
                        SELECT role, content
                        FROM (
                            SELECT role, content, created_at
                            FROM conversation_turns
                            WHERE user_id = %s
                            ORDER BY created_at DESC
                            LIMIT %s
                        ) recent
                        ORDER BY created_at ASC
                    """, (user_id, limit))
                rows = cur.fetchall()
        return [{'role': row['role'], 'content': row['content'], 'created_at': row.get('created_at')} for row in rows]

    # ==================== M1: Goals (PostgreSQL) ====================

    async def get_active_goals(self, user_id: str) -> List[Goal]:
        """
        Retrieve active goals from PostgreSQL

        YOUR QUERY LOGIC: Filter, sort by priority
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, title, description, status, priority,
                           target_date, created_at, completed_at, metadata
                    FROM goals
                    WHERE user_id = %s AND status = 'active'
                    ORDER BY priority DESC
                """, (user_id,))

                rows = cur.fetchall()
                goals = []

                for row in rows:
                    goals.append(Goal(
                        id=str(row['id']),
                        user_id=str(row['user_id']),
                        title=row['title'],
                        description=row['description'],
                        status=GoalStatus(row['status']),
                        priority=row['priority'],
                        target_date=row['target_date'],
                        created_at=row['created_at'],
                        completed_at=row['completed_at'],
                        metadata=row['metadata'] or {}
                    ))

                logger.debug(f"✅ Retrieved {len(goals)} active goals for {user_id}")
                return goals

    async def create_goal(self, goal: Goal) -> Optional[Goal]:
        """Create a new goal in PostgreSQL"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                goal_id = goal.id or str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO goals (id, user_id, title, description, status, priority, target_date, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, created_at
                """, (
                    goal_id,
                    goal.user_id,
                    goal.title,
                    goal.description,
                    goal.status.value,
                    goal.priority,
                    goal.target_date,
                    json.dumps(goal.metadata)
                ))

                result = cur.fetchone()
                goal.id = str(result[0])
                goal.created_at = result[1]

                logger.debug(f"✅ Created goal: {goal.id}")
                return goal

    # ==================== M1: Events (PostgreSQL) ====================

    async def store_event(self, event: Event) -> Optional[Event]:
        """Store a calendar event in PostgreSQL"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                event_id = event.id or str(uuid.uuid4())

                # Check if event with same source_id already exists
                if event.source_id:
                    cur.execute("""
                        SELECT id FROM events
                        WHERE source = %s AND source_id = %s
                    """, (event.source, event.source_id))

                    existing = cur.fetchone()
                    if existing:
                        # Update existing event
                        event_id = str(existing[0])
                        cur.execute("""
                            UPDATE events
                            SET title = %s, description = %s, start_time = %s, end_time = %s,
                                location = %s, metadata = %s
                            WHERE id = %s
                            RETURNING id, created_at
                        """, (
                            event.title,
                            event.description,
                            event.start_time,
                            event.end_time,
                            event.location,
                            json.dumps(event.metadata),
                            event_id
                        ))
                    else:
                        # Insert new event
                        cur.execute("""
                            INSERT INTO events (id, user_id, title, description, start_time, end_time,
                                               location, source, source_id, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id, created_at
                        """, (
                            event_id,
                            event.user_id,
                            event.title,
                            event.description,
                            event.start_time,
                            event.end_time,
                            event.location,
                            event.source,
                            event.source_id,
                            json.dumps(event.metadata)
                        ))
                else:
                    # No source_id, just insert
                    cur.execute("""
                        INSERT INTO events (id, user_id, title, description, start_time, end_time,
                                           location, source, source_id, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, created_at
                    """, (
                        event_id,
                        event.user_id,
                        event.title,
                        event.description,
                        event.start_time,
                        event.end_time,
                        event.location,
                        event.source,
                        event.source_id,
                        json.dumps(event.metadata)
                    ))

                result = cur.fetchone()
                event.id = str(result[0])
                event.created_at = result[1]

                logger.debug(f"✅ Stored event: {event.id}")
                return event

    async def get_upcoming_events(
        self, user_id: str, hours_ahead: int = 24
    ) -> List[Event]:
        """
        Get upcoming events from PostgreSQL

        YOUR TEMPORAL LOGIC: How far ahead to look
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                now = datetime.now(timezone.utc)
                cutoff = now + timedelta(hours=hours_ahead)

                cur.execute("""
                    SELECT id, user_id, title, description, start_time, end_time,
                           location, source, source_id, metadata, created_at
                    FROM events
                    WHERE user_id = %s
                      AND start_time >= %s
                      AND start_time <= %s
                    ORDER BY start_time ASC
                """, (user_id, now, cutoff))

                rows = cur.fetchall()
                events = []

                for row in rows:
                    events.append(Event(
                        id=str(row['id']),
                        user_id=str(row['user_id']),
                        title=row['title'],
                        description=row['description'],
                        start_time=row['start_time'],
                        end_time=row['end_time'],
                        location=row['location'],
                        source=row['source'],
                        source_id=row['source_id'],
                        metadata=row['metadata'] or {},
                        created_at=row['created_at']
                    ))

                logger.debug(f"✅ Retrieved {len(events)} upcoming events for {user_id}")
                return events

    # ==================== M2: Semantic Memory (Weaviate) ====================

    async def store_semantic_memory(
        self, entry: SemanticMemoryEntry
    ) -> Optional[str]:
        """
        Store content in Weaviate with embedding

        YOUR PIPELINE:
        1. Generate embedding (if not provided)
        2. Store in Weaviate
        3. Return UUID
        """
        if not self.weaviate:
            logger.warning("⚠️  Weaviate client not initialized - skipping semantic memory storage")
            return None

        try:
            # Generate embedding if not provided
            if not entry.embedding and self.embedding_service:
                entry.embedding = await self.embedding_service.generate_embedding(entry.content)

            # Store in Weaviate (ensure RFC3339 format for timestamp)
            timestamp_str = entry.timestamp.isoformat()
            if not timestamp_str.endswith('Z') and '+' not in timestamp_str:
                timestamp_str += 'Z'  # Add UTC marker if missing

            uuid_str = self.weaviate.store_memory(
                collection="ConversationMemory",
                content={
                    "user_id": entry.user_id,
                    "content": entry.content,
                    "role": entry.metadata.get("role", "user"),
                    "timestamp": timestamp_str,
                    "source": entry.source,
                    "metadata": json.dumps(entry.metadata)
                },
                vector=entry.embedding
            )

            logger.debug(f"✅ Stored semantic memory: {uuid_str}")
            return uuid_str

        except Exception as e:
            logger.error(f"❌ Failed to store semantic memory: {e}")
            return None

    async def query_semantic_memory(
        self, user_id: str, query: str, limit: int = 5, offset: int = 0
    ) -> List[SemanticMemoryEntry]:
        """
        Query Weaviate using hybrid search (semantic + keyword)

        YOUR HYBRID LOGIC: Combine vector similarity + keyword matching
        """
        if not self.weaviate:
            logger.warning("⚠️  Weaviate client not initialized - returning empty results")
            return []

        # BM25 requires a non-empty query — skip Weaviate for blank queries
        if not query or not query.strip():
            return []

        try:
            # Generate query embedding
            if self.embedding_service:
                query_embedding = await self.embedding_service.generate_query_embedding(query)
            else:
                logger.warning("⚠️  No embedding service - using keyword search only")
                results = self.weaviate.query_keyword(
                    collection="ConversationMemory",
                    query=query,
                    user_id=user_id,
                    limit=limit
                )
                return self._convert_weaviate_results(results)

            # Hybrid search (semantic + keyword)
            results = self.weaviate.hybrid_search(
                collection="ConversationMemory",
                query=query,
                query_vector=query_embedding,
                user_id=user_id,
                limit=limit,
                alpha=0.7  # 70% semantic, 30% keyword
            )

            entries = self._convert_weaviate_results(results)
            logger.debug(f"✅ Retrieved {len(entries)} semantic memories for query: {query}")
            return entries

        except Exception as e:
            logger.error(f"❌ Failed to query semantic memory: {e}")
            return []

    def _convert_weaviate_results(self, results: List[Dict[str, Any]]) -> List[SemanticMemoryEntry]:
        """Convert Weaviate results to SemanticMemoryEntry objects"""
        entries = []
        for result in results:
            props = result['properties']
            metadata = json.loads(props.get('metadata', '{}'))

            entries.append(SemanticMemoryEntry(
                id=result['uuid'],
                user_id=props['user_id'],
                content=props['content'],
                source=props['source'],
                timestamp=props['timestamp'] if isinstance(props['timestamp'], datetime) else datetime.fromisoformat(str(props['timestamp']).replace('Z', '+00:00')),
                metadata=metadata
            ))
        return entries

    async def clear_semantic_memory(self, user_id: str) -> int:
        """Clear all semantic memory for a user (use with caution!)"""
        # This would require Weaviate batch delete - not implemented in MVP
        logger.warning(f"⚠️  clear_semantic_memory called for {user_id} - not implemented in MVP")
        return 0

    # ==================== User Context (For ESL) ====================

    async def get_user_context(self, user_id: str) -> UserContext:
        """
        Get complete user context for ESL decision-making

        YOUR CONTEXT BUILDING: What to include for ethical decisions
        """
        user_values = await self.get_user_values(user_id)
        active_goals = await self.get_active_goals(user_id)
        focus_mode = await self._get_focus_mode(user_id)

        return UserContext(
            user_id=str(user_id),
            current_time=datetime.now(timezone.utc),
            focus_mode=focus_mode,
            active_goals=[goal.id for goal in active_goals if goal.id],
            user_values=user_values,
            recent_interactions=[],  # Could query semantic memory here
            additional_context={
                "goal_count": len(active_goals),
                "boundary_count": len([v for v in user_values if v.type == ValueType.BOUNDARY])
            }
        )

    # ==================== V2: Current Context (For Relevance Scoring) ====================

    async def get_current_context(self, user_id: str) -> RelevanceContext:
        """
        Get rich context for V2 relevance scoring

        YOUR V2 CONTEXT BUILDING:
        - Active goals (from M1)
        - Upcoming events (from M1)
        - Recent topics (from M2)
        - User values (from M1)
        - Focus mode (from M1)
        """
        # M1 queries
        active_goals = await self.get_active_goals(user_id)
        upcoming_events = await self.get_upcoming_events(user_id, hours_ahead=48)
        user_values = await self.get_user_values(user_id)
        focus_mode = await self._get_focus_mode(user_id)

        # M2 query for recent topics (if available)
        recent_topics = []
        if self.weaviate and self.embedding_service:
            try:
                # Get recent memories from last 24 hours
                recent_memories = await self.query_semantic_memory(
                    user_id=user_id,
                    query="recent",  # Simple query to get recent items
                    limit=10
                )
                # Extract topics from content
                recent_topics = [memory.content[:50] for memory in recent_memories[:5]]
            except Exception as e:
                logger.warning(f"⚠️  Failed to get recent topics: {e}")

        # Build rich context
        context = RelevanceContext(
            user_id=user_id,
            query=None,  # Will be set by caller
            active_goals=[goal.title for goal in active_goals],
            upcoming_events=[
                {
                    "title": event.title,
                    "start_time": event.start_time,
                    "description": event.description
                }
                for event in upcoming_events
            ],
            recent_topics=recent_topics,
            focus_mode=focus_mode,
            user_values=[value.value for value in user_values],
            time_of_day=datetime.now(timezone.utc).hour
        )

        logger.debug(f"✅ Built current context for {user_id}: {len(active_goals)} goals, {len(upcoming_events)} events")
        return context

    # ==================== Focus Mode ====================

    async def _get_focus_mode(self, user_id: str) -> bool:
        """Check if user is in focus mode from PostgreSQL"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT focus_mode
                    FROM user_sessions
                    WHERE user_id = %s
                """, (user_id,))

                row = cur.fetchone()
                return row['focus_mode'] if row else False

    async def set_focus_mode(self, user_id: str, enabled: bool) -> bool:
        """Set focus mode for a user in PostgreSQL"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_sessions (user_id, focus_mode)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET focus_mode = EXCLUDED.focus_mode,
                        updated_at = NOW()
                """, (user_id, enabled))

                logger.debug(f"✅ Set focus mode for {user_id}: {enabled}")
                return True

    async def get_recent_source_items(self, user_id: str, limit: int = 20) -> list:
        """
        Fetch recent calendar events and emails from source_items for context injection.
        Returns [] gracefully on empty table or any query failure — never raises.
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT source_type, source_item_type, title, body, item_at
                        FROM source_items
                        WHERE user_id = %s
                          AND item_at >= now() - interval '7 days'
                        ORDER BY item_at DESC
                        LIMIT %s
                        """,
                        (user_id, limit),
                    )
                    rows = cur.fetchall()
            return [
                {
                    "source_type": row["source_type"],
                    "source_item_type": row["source_item_type"],
                    "title": row["title"],
                    "body": row["body"],
                    "item_at": row["item_at"].isoformat() if row["item_at"] else None,
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"⚠️  get_recent_source_items failed: {e}")
            return []
