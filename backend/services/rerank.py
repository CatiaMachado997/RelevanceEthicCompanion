"""
Cross-encoder rerank pass (Sprint G Task 3).

Calls Jina's free-tier rerank API to reorder hybrid-search candidates by query
relevance. Falls back to raw top-K when:
  - JINA_API_KEY is empty/missing
  - The Jina API call fails (any exception)
  - The response is malformed

The fallback is the unit-test-friendly default — the chain must keep working
without a key.

Endpoint:  POST https://api.jina.ai/v1/rerank
Default model: jina-reranker-v2-base-multilingual
Free tier:    ~100 RPM
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
DEFAULT_MODEL = "jina-reranker-v2-base-multilingual"
DEFAULT_TIMEOUT = 10.0


async def rerank(
    query: str,
    candidates: list[dict],
    *,
    top_k: int = 5,
    api_key: str | None = None,
    model: str | None = None,
    text_field: str = "snippet",
) -> list[dict]:
    """Rerank a list of candidate chunks by query relevance using Jina API.

    Each candidate is a dict containing at least `text_field` (default
    "snippet"). Returns up to `top_k` candidates, sorted by rerank_score
    descending (Jina returns them already sorted; we respect their order).
    Each kept candidate gets a new key `rerank_score` (float).

    Falls back to `candidates[:top_k]` (unchanged order, no rerank_score)
    when the API key is missing, the call fails, or the response is malformed.
    """
    if not candidates:
        return []

    if not api_key:
        logger.debug("Rerank skipped — no JINA_API_KEY; returning raw top-K")
        return candidates[:top_k]

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
        logger.debug(f"Rerank fell back to raw top-K — Jina call failed: {e}")
        return candidates[:top_k]

    try:
        results = data["results"]
        reranked: list[dict] = []
        for entry in results:
            idx = entry["index"]
            score = float(entry["relevance_score"])
            if 0 <= idx < len(candidates):
                item = dict(candidates[idx])
                item["rerank_score"] = score
                reranked.append(item)
        if not reranked:
            raise ValueError("empty rerank result set")
    except Exception as e:
        logger.debug(f"Rerank fell back to raw top-K — malformed response: {e}")
        return candidates[:top_k]

    logger.info(
        f"Rerank applied — {len(candidates)} candidates → {len(reranked)} "
        f"(model={model_name})"
    )
    return reranked[:top_k]
