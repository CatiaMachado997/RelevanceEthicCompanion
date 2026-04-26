"""
RAG retrieval service.

Hybrid search (dense + BM25, alpha=0.7) over the user's `DocumentMemory`
collection in Weaviate. Returns structured citation rows the chat layer
attaches to the assistant turn so the frontend can render source cards.

Reuses:
  - EmbeddingService.generate_query_embedding (retrieval-optimized task type)
  - WeaviateClient.hybrid_search (already used by /api/search)

Degrades gracefully: returns [] if Weaviate is offline or query embedding
fails — the chat turn must never break because retrieval is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from config import settings
from services.embedding_service import EmbeddingService
from utils.weaviate_client import get_weaviate_client

logger = logging.getLogger(__name__)

DOCUMENT_COLLECTION = "DocumentMemory"
DEFAULT_K = 5
DEFAULT_ALPHA = 0.7  # Favors dense vector with meaningful BM25 contribution.


_embedding_service: EmbeddingService | None = None


def _get_embedding_service() -> EmbeddingService:
    """Lazy singleton — avoids constructing the Gemini client at import time."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(settings.GEMINI_API_KEY)
    return _embedding_service


class RagRetrievalService:
    """Retrieve grounded document chunks for a user query."""

    async def retrieve(
        self,
        query: str,
        user_id: str,
        k: int = DEFAULT_K,
    ) -> list[dict[str, Any]]:
        """Return up to `k` document chunks relevant to `query` for `user_id`.

        Result shape (one row per chunk):
            {
                "chunk_uuid": str,        # Weaviate object UUID
                "document_id": str,
                "filename": str,
                "chunk_index": int,
                "snippet": str,           # the chunk content
                "score": float,           # hybrid fusion score
                "source_type": str,       # "document" | "gmail" | "slack" | ...
            }

        Returns an empty list when Weaviate is unavailable or any error
        occurs — never raises into the caller's chat turn.
        """
        weaviate = get_weaviate_client()
        if weaviate is None:
            logger.info("RAG retrieval skipped — Weaviate unavailable")
            return []

        try:
            embedder = _get_embedding_service()
            query_vector = await embedder.generate_query_embedding(query)
        except Exception as e:
            logger.warning(f"RAG retrieval skipped — query embedding failed: {e}")
            return []

        try:
            raw = weaviate.hybrid_search(
                collection=DOCUMENT_COLLECTION,
                query=query,
                query_vector=query_vector,
                user_id=str(user_id),
                limit=k,
                alpha=DEFAULT_ALPHA,
            )
        except Exception as e:
            logger.warning(f"RAG retrieval failed in Weaviate hybrid_search: {e}")
            return []

        return [self._format(item) for item in raw]

    @staticmethod
    def _format(item: dict[str, Any]) -> dict[str, Any]:
        props = item.get("properties") or {}
        return {
            "chunk_uuid": item.get("uuid"),
            "document_id": props.get("document_id"),
            "filename": props.get("filename"),
            "chunk_index": props.get("chunk_index"),
            "snippet": props.get("content") or "",
            "score": item.get("score") or 0.0,
            "source_type": props.get("source_type") or "document",
        }
