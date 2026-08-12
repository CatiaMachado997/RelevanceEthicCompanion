"""
RAG retrieval service.

Hybrid search (dense + BM25, alpha=0.5) over the user's `DocumentMemory`
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
import os
import re
from collections import Counter
from typing import Any

from config import settings
from services.deepeval_tracing import observe_retriever, update_retriever_span
from services.embedding_service import EmbeddingService
from services.rag_query import (
    build_retrieval_queries,
    reciprocal_rank_fusion,
    retrieval_query_weights,
)
from services.rerank import rerank
from utils.weaviate_client import get_weaviate_client

logger = logging.getLogger(__name__)

DOCUMENT_COLLECTION = "DocumentMemory"
DEFAULT_K = int(os.getenv("RAG_DEFAULT_K", "5"))
DEFAULT_ALPHA = float(os.getenv("RAG_HYBRID_ALPHA", "0.5"))
# Sprint G Task 3: pull a wider candidate pool from hybrid search so the
# cross-encoder reranker has more to choose from. Floor of 20 keeps recall
# healthy even when the caller asks for a small top-K.
RERANK_CANDIDATE_FLOOR = int(os.getenv("RAG_CANDIDATE_FLOOR", "20"))
RRF_K = int(os.getenv("RAG_RRF_K", str(settings.RAG_RRF_K)))
ORIGINAL_QUERY_WEIGHT = float(
    os.getenv("RAG_ORIGINAL_QUERY_WEIGHT", str(settings.RAG_ORIGINAL_QUERY_WEIGHT))
)
QUERY_EXPANSION_ENABLED = os.getenv("RAG_QUERY_EXPANSION", "0") == "1"
QUERY_EXPANSION_WEIGHT = float(os.getenv("RAG_QUERY_EXPANSION_WEIGHT", "0.8"))
METADATA_RERANK_WEIGHT = float(os.getenv("RAG_METADATA_RERANK_WEIGHT", "0"))
MAX_CHUNKS_PER_DOCUMENT = int(
    os.getenv(
        "RAG_MAX_CHUNKS_PER_DOCUMENT",
        str(settings.RAG_MAX_CHUNKS_PER_DOCUMENT),
    )
)
NEAR_DUPLICATE_THRESHOLD = float(
    os.getenv(
        "RAG_NEAR_DUPLICATE_THRESHOLD",
        str(settings.RAG_NEAR_DUPLICATE_THRESHOLD),
    )
)
NEIGHBOR_WINDOW = int(
    os.getenv("RAG_NEIGHBOR_WINDOW", str(settings.RAG_NEIGHBOR_WINDOW))
)
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


_embedding_service: EmbeddingService | None = None


def _content_terms(row: dict[str, Any]) -> set[str]:
    return set(_WORD.findall(str(row.get("snippet") or "").lower()))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def select_diverse_results(
    ranked: list[dict[str, Any]],
    *,
    top_k: int,
    max_per_document: int = MAX_CHUNKS_PER_DOCUMENT,
    duplicate_threshold: float = NEAR_DUPLICATE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Suppress duplicates and prevent one document from crowding out others."""
    selected: list[dict[str, Any]] = []
    selected_terms: list[set[str]] = []
    per_document: Counter[str] = Counter()
    seen_ids: set[str] = set()

    for row in ranked:
        key = str(row.get("chunk_uuid") or "")
        document_id = str(row.get("document_id") or key)
        terms = _content_terms(row)
        if key in seen_ids or per_document[document_id] >= max_per_document:
            continue
        if any(
            _jaccard(terms, existing) >= duplicate_threshold
            for existing in selected_terms
        ):
            continue
        selected.append(row)
        selected_terms.append(terms)
        seen_ids.add(key)
        per_document[document_id] += 1
        if len(selected) == top_k:
            return selected

    # Preserve the requested result count when the corpus contains only one
    # document or many near-identical chunks.
    for row in ranked:
        key = str(row.get("chunk_uuid") or "")
        if key and key not in seen_ids:
            selected.append(row)
            seen_ids.add(key)
        if len(selected) == top_k:
            break
    return selected


def expand_with_candidate_neighbors(
    selected: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    window: int = NEIGHBOR_WINDOW,
) -> list[dict[str, Any]]:
    """Attach adjacent candidate chunks for generation without changing citations."""
    if window <= 0:
        return selected
    by_document: dict[str, dict[int, dict[str, Any]]] = {}
    for row in candidates:
        document_id = str(row.get("document_id") or "")
        chunk_index = row.get("chunk_index")
        if document_id and isinstance(chunk_index, int):
            by_document.setdefault(document_id, {})[chunk_index] = row

    expanded: list[dict[str, Any]] = []
    for item in selected:
        row = dict(item)
        document_id = str(row.get("document_id") or "")
        chunk_index = row.get("chunk_index")
        neighbors = by_document.get(document_id, {})
        if isinstance(chunk_index, int) and neighbors:
            indexes = range(chunk_index - window, chunk_index + window + 1)
            parts = [neighbors[index] for index in indexes if index in neighbors]
            if len(parts) > 1:
                row["expanded_snippet"] = "\n\n".join(
                    str(part.get("snippet") or "") for part in parts
                )
                row["neighbor_chunk_uuids"] = [
                    part.get("chunk_uuid")
                    for part in parts
                    if part.get("chunk_uuid") != row.get("chunk_uuid")
                ]
        expanded.append(row)
    return expanded


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

    @observe_retriever
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
            "retrieval_queries": [],
            "candidates": [],
            "rerank_applied": False,
            "rerank_top": None,
            "final": [],
            "final_document_ids": [],
        }

        weaviate = get_weaviate_client()
        if weaviate is None:
            logger.info("RAG retrieval skipped — Weaviate unavailable")
            return [], trace

        try:
            embedder = _get_embedding_service()
            retrieval_queries = build_retrieval_queries(
                query, expand=QUERY_EXPANSION_ENABLED
            )
            trace["retrieval_queries"] = retrieval_queries
            query_vectors = [
                await embedder.generate_query_embedding(retrieval_query)
                for retrieval_query in retrieval_queries
            ]
        except Exception as e:
            logger.warning(f"RAG retrieval skipped — query embedding failed: {e}")
            return [], trace

        # Sprint G Task 3: fetch a wider candidate pool so the reranker has
        # meaningful choices. The reranker (or fallback) trims back to `k`.
        candidate_limit = max(RERANK_CANDIDATE_FLOOR, k)
        try:
            ranked_lists = [
                weaviate.hybrid_search(
                    collection=DOCUMENT_COLLECTION,
                    query=retrieval_query,
                    query_vector=query_vector,
                    user_id=str(user_id),
                    limit=candidate_limit,
                    alpha=DEFAULT_ALPHA,
                    embedding_model=embedder.model,
                )
                for retrieval_query, query_vector in zip(
                    retrieval_queries, query_vectors
                )
            ]
            weights = retrieval_query_weights(
                query,
                retrieval_queries,
                original_weight=ORIGINAL_QUERY_WEIGHT,
                expansion_weight=QUERY_EXPANSION_WEIGHT,
            )
            raw = reciprocal_rank_fusion(
                ranked_lists, rank_constant=RRF_K, weights=weights
            )
        except Exception as e:
            logger.warning(f"RAG retrieval failed in Weaviate hybrid_search: {e}")
            return [], trace

        candidates = [self._format(item) for item in raw]
        trace["candidates"] = [
            {
                "chunk_uuid": c.get("chunk_uuid"),
                "document_id": c.get("document_id"),
                "filename": c.get("filename"),
                "section_title": c.get("section_title"),
                "language": c.get("language"),
                "hybrid_score": float(c.get("hybrid_score") or c.get("score") or 0.0),
                "snippet_preview": (c.get("snippet") or "")[:200],
            }
            for c in candidates
        ]

        # Cross-encoder rerank pass — graceful no-op if JINA_API_KEY is empty
        # or the call fails. Returns at most `k` rows.
        reranked = await rerank(
            retrieval_queries[0],
            candidates,
            top_k=len(candidates),
            api_key=settings.JINA_API_KEY,
            model=settings.RERANK_MODEL,
            provider=settings.RAG_RERANK_PROVIDER,
            metadata_weight=METADATA_RERANK_WEIGHT,
        )
        results = select_diverse_results(reranked, top_k=k)
        results = expand_with_candidate_neighbors(results, candidates)

        # `rerank()` annotates kept candidates with `rerank_score` on success
        # and falls back to `candidates[:top_k]` (no key) on missing-key/error.
        rerank_applied = any("rerank_score" in r for r in results)
        trace["rerank_applied"] = rerank_applied
        if rerank_applied:
            trace["rerank_top"] = [
                {
                    "chunk_uuid": r.get("chunk_uuid"),
                    "rerank_score": float(r.get("rerank_score") or 0.0),
                    "rerank_provider": r.get("rerank_provider"),
                }
                for r in results
            ]
        else:
            trace["rerank_top"] = None

        trace["final"] = [r.get("chunk_uuid") for r in results]
        trace["final_document_ids"] = [r.get("document_id") for r in results]
        update_retriever_span(
            query=query,
            results=results,
            metadata={
                "user_id": str(user_id),
                "candidate_count": len(candidates),
                "returned_count": len(results),
                "rerank_applied": rerank_applied,
                "alpha": DEFAULT_ALPHA,
                "k": k,
                "retrieval_queries": retrieval_queries,
                "embedding_model": embedder.model,
                "rerank_provider": settings.RAG_RERANK_PROVIDER,
            },
        )
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
            "hybrid_score": item.get("hybrid_score") or item.get("score") or 0.0,
            "source_type": props.get("source_type") or "document",
            "embedding_model": props.get("embedding_model"),
            "section_title": props.get("section_title") or "",
            "language": props.get("language") or "",
            "document_version": props.get("document_version") or "",
        }
