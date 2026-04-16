"""
Weaviate Client Wrapper
Manages connection and operations for M2 (semantic memory)
"""

import weaviate
from weaviate.classes.query import Filter
from typing import List, Dict, Any, Optional
import logging
import time
from datetime import datetime

from weaviate_config import WEAVIATE_SCHEMAS

logger = logging.getLogger(__name__)


class WeaviateClient:
    """Wrapper for Weaviate operations with schema management"""

    def __init__(self, url: str = "http://localhost:8080"):
        """
        Initialize Weaviate client

        Args:
            url: Weaviate server URL (default: http://localhost:8080)
        """
        self.url = url
        self.client = None
        self._connect()

    def _connect(self):
        """Establish connection to Weaviate"""
        try:
            self.client = weaviate.connect_to_local(
                host="localhost",
                port=8080,
                grpc_port=50051,
                skip_init_checks=False,  # Try with gRPC enabled
            )
            logger.info(f"✅ Connected to Weaviate at {self.url} (with gRPC)")
        except Exception as e:
            logger.warning(
                f"⚠️  gRPC connection failed, falling back to HTTP-only: {e}"
            )
            try:
                # Fallback to HTTP-only if gRPC fails
                self.client = weaviate.connect_to_local(
                    host="localhost", port=8080, skip_init_checks=True
                )
                logger.info(f"✅ Connected to Weaviate at {self.url} (HTTP-only mode)")
            except Exception as e2:
                logger.error(f"❌ Failed to connect to Weaviate: {e2}")
                raise

    def initialize_schemas(self):
        """Create all collection schemas if they don't exist"""
        try:
            for schema in WEAVIATE_SCHEMAS:
                class_name = schema["class"]

                # Check if collection exists
                if self.client.collections.exists(class_name):
                    logger.info(f"Collection {class_name} already exists")
                    continue

                # Create collection
                self.client.collections.create_from_dict(schema)
                logger.info(f"✅ Created collection: {class_name}")

            logger.info("✅ All Weaviate schemas initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize schemas: {e}")
            raise

    def store_memory(
        self, collection: str, content: Dict[str, Any], vector: List[float]
    ) -> str:
        """
        Store a memory entry with embedding

        Args:
            collection: Collection name (ConversationMemory, ContextualEvents, UserGoals)
            content: Dictionary of properties (must match schema)
            vector: Embedding vector from Gemini

        Returns:
            UUID of the created object
        """
        try:
            collection_obj = self.client.collections.get(collection)

            # Convert datetime objects to ISO strings
            for key, value in content.items():
                if isinstance(value, datetime):
                    content[key] = value.isoformat()

            # Add object with vector
            uuid = collection_obj.data.insert(properties=content, vector=vector)

            logger.debug(f"✅ Stored memory in {collection}: {uuid}")
            return str(uuid)
        except Exception as e:
            logger.error(f"❌ Failed to store memory: {e}")
            raise

    def query_semantic(
        self,
        collection: str,
        query_vector: List[float],
        user_id: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query collection using semantic search (vector similarity)

        Args:
            collection: Collection name
            query_vector: Query embedding from Gemini
            user_id: Firebase UID to filter results
            limit: Maximum number of results
            filters: Additional filter conditions

        Returns:
            List of matching objects with content and distance
        """
        try:
            collection_obj = self.client.collections.get(collection)

            # Build filter using Weaviate v4 Filter class
            where_filter = Filter.by_property("user_id").equal(user_id)

            # Add additional filters if provided (not implemented in MVP)
            # Could extend here with AND/OR logic using Filter class

            # Execute near_vector query
            response = collection_obj.query.near_vector(
                near_vector=query_vector,
                limit=limit,
                return_metadata=["distance"],
                filters=where_filter,  # Note: 'filters' not 'where' in v4
            )

            # Format results
            results = []
            for obj in response.objects:
                results.append(
                    {
                        "uuid": str(obj.uuid),
                        "properties": obj.properties,
                        "distance": obj.metadata.distance if obj.metadata else None,
                    }
                )

            logger.debug(
                f"✅ Semantic query returned {len(results)} results from {collection}"
            )
            return results
        except Exception as e:
            logger.error(f"❌ Semantic query failed: {e}")
            raise

    def query_keyword(
        self,
        collection: str,
        query: str,
        user_id: str,
        limit: int = 5,
        properties: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query collection using keyword search (BM25)

        Args:
            collection: Collection name
            query: Search query string
            user_id: Firebase UID to filter results
            limit: Maximum number of results
            properties: Properties to search in (default: all text properties)

        Returns:
            List of matching objects
        """
        try:
            collection_obj = self.client.collections.get(collection)

            # Build filter using Weaviate v4 Filter class
            where_filter = Filter.by_property("user_id").equal(user_id)

            # Execute BM25 query
            response = collection_obj.query.bm25(
                query=query,
                limit=limit,
                return_metadata=["score"],
                filters=where_filter,  # Note: 'filters' not 'where' in v4
                query_properties=properties,
            )

            # Format results
            results = []
            for obj in response.objects:
                results.append(
                    {
                        "uuid": str(obj.uuid),
                        "properties": obj.properties,
                        "score": obj.metadata.score if obj.metadata else None,
                    }
                )

            logger.debug(
                f"✅ Keyword query returned {len(results)} results from {collection}"
            )
            return results
        except Exception as e:
            logger.error(f"❌ Keyword query failed: {e}")
            raise

    def hybrid_search(
        self,
        collection: str,
        query: str,
        query_vector: List[float],
        user_id: str,
        limit: int = 5,
        alpha: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic (vector) and keyword (BM25)

        Args:
            collection: Collection name
            query: Search query string for BM25
            query_vector: Query embedding for semantic search
            user_id: Firebase UID to filter results
            limit: Maximum number of results
            alpha: Balance between vector (1.0) and keyword (0.0) search

        Returns:
            List of matching objects ranked by combined score
        """
        try:
            collection_obj = self.client.collections.get(collection)

            # Build filter using Weaviate v4 Filter class
            where_filter = Filter.by_property("user_id").equal(user_id)

            # Execute hybrid query
            response = collection_obj.query.hybrid(
                query=query,
                vector=query_vector,
                limit=limit,
                alpha=alpha,
                return_metadata=["score"],
                filters=where_filter,  # Note: 'filters' not 'where' in v4
            )

            # Format results
            results = []
            for obj in response.objects:
                results.append(
                    {
                        "uuid": str(obj.uuid),
                        "properties": obj.properties,
                        "score": obj.metadata.score if obj.metadata else None,
                    }
                )

            logger.debug(
                f"✅ Hybrid search returned {len(results)} results from {collection}"
            )
            return results
        except Exception as e:
            logger.error(f"❌ Hybrid search failed: {e}")
            raise

    def delete_by_id(self, collection: str, uuid: str):
        """Delete an object by UUID"""
        try:
            collection_obj = self.client.collections.get(collection)
            collection_obj.data.delete_by_id(uuid)
            logger.debug(f"✅ Deleted object {uuid} from {collection}")
        except Exception as e:
            logger.error(f"❌ Failed to delete object: {e}")
            raise

    def close(self):
        """Close Weaviate connection"""
        if self.client:
            self.client.close()
            logger.info("👋 Weaviate connection closed")


# Global client instance
_weaviate_client: Optional[WeaviateClient] = None
_weaviate_unavailable: bool = False
_weaviate_last_probe: float = 0.0
_WEAVIATE_PROBE_TTL = 30.0  # seconds between liveness checks


def get_weaviate_client() -> Optional[WeaviateClient]:
    """Get or create singleton Weaviate client.

    Returns None gracefully if Weaviate is unavailable so the app can start
    and serve requests without semantic memory (M2 degraded mode).

    Uses a TTL-gated liveness probe to avoid an HTTP round-trip on every call.
    When the probe is due, is_ready() returning False (not raising) is treated
    as a stale connection and triggers a reconnect attempt.
    """
    global _weaviate_client, _weaviate_unavailable, _weaviate_last_probe

    now = time.monotonic()

    # Short-circuit if we already know it's down (until explicit close/reset)
    if _weaviate_unavailable:
        return None

    # If we have a client, do a TTL-gated liveness probe
    if _weaviate_client is not None:
        if now - _weaviate_last_probe < _WEAVIATE_PROBE_TTL:
            return _weaviate_client  # recent probe passed, skip
        # Probe is due — check if client is still alive
        try:
            inner = getattr(_weaviate_client, "client", None)
            ready = inner.is_ready() if inner is not None else False
            if ready:
                _weaviate_last_probe = now
                return _weaviate_client
            # is_ready() returned False — treat as stale
        except Exception:
            pass
        # Client is stale — reset and fall through to reconnect
        logger.warning("Weaviate connection lost — attempting reconnect")
        _weaviate_client = None
        _weaviate_unavailable = False

    # Try to connect
    try:
        _weaviate_client = WeaviateClient()
        _weaviate_client.initialize_schemas()
        _weaviate_last_probe = time.monotonic()
        return _weaviate_client
    except Exception as e:
        logger.warning(f"Weaviate unavailable — running without semantic memory: {e}")
        _weaviate_unavailable = True
        return None


def close_weaviate_client():
    """Close singleton Weaviate client"""
    global _weaviate_client, _weaviate_unavailable, _weaviate_last_probe
    if _weaviate_client:
        _weaviate_client.close()
        _weaviate_client = None
    _weaviate_unavailable = False
    _weaviate_last_probe = 0.0
