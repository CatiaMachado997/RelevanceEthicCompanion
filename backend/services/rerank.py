"""
Cross-encoder rerank pass (Sprint G Task 3).

Uses Jina's cross-encoder when configured and a lightweight local IDF reranker
otherwise. The local path adds no model process or duplicate vector store and
keeps retrieval useful when the hosted provider is unavailable.

The fallback is the unit-test-friendly default — the chain must keep working
without a key.

Endpoint:  POST https://api.jina.ai/v1/rerank
Default model: jina-reranker-v2-base-multilingual
Free tier:    ~100 RPM
"""

from __future__ import annotations

import logging
import math
import os
import re
from collections import Counter

import httpx

logger = logging.getLogger(__name__)

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
DEFAULT_MODEL = "jina-reranker-v2-base-multilingual"
DEFAULT_TIMEOUT = 10.0
DEFAULT_METADATA_WEIGHT = float(os.getenv("RAG_METADATA_RERANK_WEIGHT", "0"))
DEFAULT_LEXICAL_WEIGHT = float(os.getenv("RAG_LOCAL_RERANK_LEXICAL_WEIGHT", "0.2"))
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "da",
    "de",
    "do",
    "e",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "para",
    "that",
    "the",
    "to",
    "um",
    "uma",
    "with",
}


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall((text or "").lower())
        if len(token) > 1 and token not in _STOPWORDS
    ]


def local_rerank(
    query: str,
    candidates: list[dict],
    *,
    top_k: int,
    text_field: str = "snippet",
    metadata_weight: float = DEFAULT_METADATA_WEIGHT,
    lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
) -> list[dict]:
    """Rerank locally using query-term IDF coverage plus the hybrid score."""
    if not candidates:
        return []
    query_terms = set(_tokens(query))
    if not 0 <= metadata_weight <= 0.4:
        raise ValueError("metadata_weight must be between 0 and 0.4")
    if not 0 <= lexical_weight <= 0.8:
        raise ValueError("lexical_weight must be between 0 and 0.8")
    if lexical_weight + metadata_weight > 0.8:
        raise ValueError("lexical and metadata weights must total at most 0.8")
    documents = [set(_tokens(str(item.get(text_field, "")))) for item in candidates]
    metadata_documents = [
        set(
            _tokens(
                " ".join(
                    str(item.get(field, ""))
                    for field in (
                        "filename",
                        "section_title",
                        "document_version",
                        "source_type",
                        "language",
                    )
                )
            )
        )
        for item in candidates
    ]
    document_frequency = Counter(
        term for document in documents for term in document.intersection(query_terms)
    )
    weights = {
        term: math.log((len(documents) + 1) / (document_frequency[term] + 1)) + 1
        for term in query_terms
    }
    total_weight = sum(weights.values()) or 1.0
    hybrid_scores = [float(item.get("score") or 0.0) for item in candidates]
    low, high = min(hybrid_scores), max(hybrid_scores)

    ranked: list[dict] = []
    for item, document, metadata, hybrid in zip(
        candidates, documents, metadata_documents, hybrid_scores
    ):
        lexical = sum(weights[term] for term in query_terms.intersection(document))
        lexical /= total_weight
        metadata_score = sum(
            weights[term] for term in query_terms.intersection(metadata)
        )
        metadata_score /= total_weight
        normalized_hybrid = (hybrid - low) / (high - low) if high > low else 1.0
        # The hybrid retriever already carries strong semantic evidence. The
        # local scorer acts as a conservative lexical correction, not a reset.
        score = (
            lexical_weight * lexical
            + metadata_weight * metadata_score
            + (1.0 - lexical_weight - metadata_weight) * normalized_hybrid
        )
        row = dict(item)
        row["rerank_score"] = score
        row["rerank_provider"] = "local-idf"
        row["metadata_score"] = metadata_score
        ranked.append(row)
    ranked.sort(key=lambda row: float(row["rerank_score"]), reverse=True)
    return ranked[:top_k]


async def rerank(
    query: str,
    candidates: list[dict],
    *,
    top_k: int = 5,
    api_key: str | None = None,
    model: str | None = None,
    text_field: str = "snippet",
    provider: str = "auto",
    metadata_weight: float = DEFAULT_METADATA_WEIGHT,
    lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
) -> list[dict]:
    """Rerank a list of candidate chunks by query relevance using Jina API.

    Each candidate is a dict containing at least `text_field` (default
    "snippet"). Returns up to `top_k` candidates, sorted by rerank_score
    descending (Jina returns them already sorted; we respect their order).
    Each kept candidate gets a new key `rerank_score` (float).

    `provider="auto"` prefers Jina when a key exists and otherwise uses the
    local scorer. Jina failures also fall back locally.
    """
    if not candidates:
        return []

    provider = (provider or "auto").lower()
    if provider == "none":
        return candidates[:top_k]
    if provider not in {"auto", "jina", "local"}:
        raise ValueError("Rerank provider must be one of: auto, jina, local, none")
    if provider == "local" or not api_key:
        return local_rerank(
            query,
            candidates,
            top_k=top_k,
            text_field=text_field,
            metadata_weight=metadata_weight,
            lexical_weight=lexical_weight,
        )

    model_name = model or DEFAULT_MODEL
    documents = [str(c.get(text_field, "")) for c in candidates]
    payload = {
        "model": model_name,
        "query": query,
        "documents": documents,
        "top_n": top_k,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(JINA_RERANK_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.debug(f"Jina rerank failed; using local reranker: {e}")
        return local_rerank(
            query,
            candidates,
            top_k=top_k,
            text_field=text_field,
            metadata_weight=metadata_weight,
            lexical_weight=lexical_weight,
        )

    try:
        results = data["results"]
        reranked: list[dict] = []
        for entry in results:
            idx = entry["index"]
            score = float(entry["relevance_score"])
            if 0 <= idx < len(candidates):
                item = dict(candidates[idx])
                item["rerank_score"] = score
                item["rerank_provider"] = "jina"
                reranked.append(item)
        if not reranked:
            raise ValueError("empty rerank result set")
    except Exception as e:
        logger.debug(f"Malformed Jina response; using local reranker: {e}")
        return local_rerank(
            query,
            candidates,
            top_k=top_k,
            text_field=text_field,
            metadata_weight=metadata_weight,
            lexical_weight=lexical_weight,
        )

    logger.info(
        f"Rerank applied — {len(candidates)} candidates → {len(reranked)} "
        f"(model={model_name})"
    )
    return reranked[:top_k]
