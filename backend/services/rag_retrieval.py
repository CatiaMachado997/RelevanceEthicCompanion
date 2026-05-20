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
from services.rerank import rerank
from utils.weaviate_client import get_weaviate_client

logger = logging.getLogger(__name__)

DOCUMENT_COLLECTION = "DocumentMemory"
DEFAULT_K = 5
DEFAULT_ALPHA = 0.7  # Favors dense vector with meaningful BM25 contribution.
# Sprint G Task 3: pull a wider candidate pool from hybrid search so the
# cross-encoder reranker has more to choose from. Floor of 20 keeps recall
# healthy even when the caller asks for a small top-K.
RERANK_CANDIDATE_FLOOR = 20


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

        Backwards-compatible wrapper around :meth:`retrieve_with_trace` that
        discards the breadcrumb trace. New callers that want to surface the
        retrieval breadcrumbs in Transparency should call
        :meth:`retrieve_with_trace` directly.
        """
        results, _trace = await self.retrieve_with_trace(query, user_id, k=k)
        return results

    async def retrieve_with_trace(
        self,
        query: str,
        user_id: str,
        k: int = DEFAULT_K,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Sprint G Task 4: retrieve + a structured breadcrumb `trace`.

        The trace mirrors the retrieval pipeline so the Transparency panel
        can show exactly which chunks were considered, which were reranked,
        and which were finally cited.

        Trace shape::

            {
                "query": str,
                "candidates": [
                    {"chunk_uuid", "hybrid_score", "snippet_preview"},  # all hybrid candidates pre-rerank
                    ...
                ],
                "rerank_applied": bool,            # True iff Jina was actually called and succeeded
                "rerank_top": [{"chunk_uuid", "rerank_score"}, ...] | None,
                "final": [chunk_uuid, ...],        # chunk_uuids of returned results, in order
            }

        Always builds a trace, even on failure paths — empty candidates and
        `final=[]` when Weaviate is unavailable or hybrid search fails.
        """
        trace: dict[str, Any] = {
            "query": query,
            "candidates": [],
            "rerank_applied": False,
            "rerank_top": None,
            "final": [],
        }

        weaviate = get_weaviate_client()
        if weaviate is None:
            logger.info("RAG retrieval skipped — Weaviate unavailable")
            return [], trace

        try:
            embedder = _get_embedding_service()
            query_vector = await embedder.generate_query_embedding(query)
        except Exception as e:
            logger.warning(f"RAG retrieval skipped — query embedding failed: {e}")
            return [], trace

        # Sprint G Task 3: fetch a wider candidate pool so the reranker has
        # meaningful choices. The reranker (or fallback) trims back to `k`.
        candidate_limit = max(RERANK_CANDIDATE_FLOOR, k)
        try:
            raw = weaviate.hybrid_search(
                collection=DOCUMENT_COLLECTION,
                query=query,
                query_vector=query_vector,
                user_id=str(user_id),
                limit=candidate_limit,
                alpha=DEFAULT_ALPHA,
            )
        except Exception as e:
            logger.warning(f"RAG retrieval failed in Weaviate hybrid_search: {e}")
            return [], trace

        candidates = [self._format(item) for item in raw]
        trace["candidates"] = [
            {
                "chunk_uuid": c.get("chunk_uuid"),
                "hybrid_score": float(c.get("score") or 0.0),
                "snippet_preview": (c.get("snippet") or "")[:200],
            }
            for c in candidates
        ]

        # Cross-encoder rerank pass — graceful no-op if JINA_API_KEY is empty
        # or the call fails. Returns at most `k` rows.
        results = await rerank(
            query,
            candidates,
            top_k=k,
            api_key=settings.JINA_API_KEY,
            model=settings.RERANK_MODEL,
        )

        # `rerank()` annotates kept candidates with `rerank_score` on success
        # and falls back to `candidates[:top_k]` (no key) on missing-key/error.
        rerank_applied = any("rerank_score" in r for r in results)
        trace["rerank_applied"] = rerank_applied
        if rerank_applied:
            trace["rerank_top"] = [
                {
                    "chunk_uuid": r.get("chunk_uuid"),
                    "rerank_score": float(r.get("rerank_score") or 0.0),
                }
                for r in results
            ]
        else:
            trace["rerank_top"] = None

        trace["final"] = [r.get("chunk_uuid") for r in results]
        return results, trace

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
