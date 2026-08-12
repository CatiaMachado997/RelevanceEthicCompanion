"""Tests for services.rerank — Jina cross-encoder rerank with graceful fallback."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from services.rerank import rerank

# Capture the unpatched class so our patches' side_effects don't recurse
# into the patched name when constructing a transport-backed client.
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _make_client_factory(transport: httpx.MockTransport):
    """Build a side_effect for the AsyncClient patch that uses MockTransport."""
    return lambda **kw: _REAL_ASYNC_CLIENT(transport=transport, timeout=10.0)


def _candidates(n: int = 4) -> list[dict]:
    return [
        {"chunk_uuid": f"u-{i}", "snippet": f"chunk text {i}", "score": 0.5}
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_rerank_uses_local_scorer_without_key():
    """Empty API key uses the dependency-free local relevance scorer."""
    cands = _candidates(4)

    with patch("services.rerank.httpx.AsyncClient") as client_cls:
        result = await rerank("anything", cands, top_k=3, api_key="")

    # No HTTP client should have been constructed.
    client_cls.assert_not_called()
    assert len(result) == 3
    for r in result:
        assert "rerank_score" in r
        assert r["rerank_provider"] == "local-idf"


@pytest.mark.asyncio
async def test_rerank_falls_back_on_http_error():
    """If Jina fails, fall back to the local scorer."""
    cands = _candidates(4)

    def _raise(*args, **kwargs):
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(_raise)

    with patch(
        "services.rerank.httpx.AsyncClient",
        side_effect=_make_client_factory(transport),
    ):
        result = await rerank("query", cands, top_k=2, api_key="fake-key")

    assert len(result) == 2
    assert [r["chunk_uuid"] for r in result] == ["u-0", "u-1"]
    for r in result:
        assert "rerank_score" in r
        assert r["rerank_provider"] == "local-idf"


@pytest.mark.asyncio
async def test_rerank_sorts_by_jina_response():
    """Jina response order is respected; indices map back to original candidates."""
    cands = _candidates(4)

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        # Sanity-check the request payload.
        assert body["query"] == "what is the answer"
        assert body["documents"] == [c["snippet"] for c in cands]
        assert body["top_n"] == 5
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 2, "relevance_score": 0.95},
                    {"index": 0, "relevance_score": 0.7},
                ]
            },
        )

    transport = httpx.MockTransport(_handler)

    with patch(
        "services.rerank.httpx.AsyncClient",
        side_effect=_make_client_factory(transport),
    ):
        result = await rerank("what is the answer", cands, top_k=5, api_key="fake-key")

    assert [r["chunk_uuid"] for r in result] == ["u-2", "u-0"]
    assert result[0]["rerank_score"] == 0.95
    assert result[0]["rerank_provider"] == "jina"
    assert result[1]["rerank_score"] == 0.7
    # Original fields preserved.
    assert result[0]["snippet"] == "chunk text 2"


@pytest.mark.asyncio
async def test_rerank_respects_top_k():
    """top_k=2 with 5 candidates → 2 returned (even when Jina returns more)."""
    cands = _candidates(5)

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 4, "relevance_score": 0.99},
                    {"index": 1, "relevance_score": 0.88},
                    {"index": 2, "relevance_score": 0.77},
                ]
            },
        )

    transport = httpx.MockTransport(_handler)

    with patch(
        "services.rerank.httpx.AsyncClient",
        side_effect=_make_client_factory(transport),
    ):
        result = await rerank("q", cands, top_k=2, api_key="fake-key")

    assert len(result) == 2
    assert [r["chunk_uuid"] for r in result] == ["u-4", "u-1"]


@pytest.mark.asyncio
async def test_rerank_empty_candidates_short_circuits():
    """No candidates → no HTTP call, return []."""
    with patch("services.rerank.httpx.AsyncClient") as client_cls:
        result = await rerank("q", [], top_k=5, api_key="fake-key")
    client_cls.assert_not_called()
    assert result == []


@pytest.mark.asyncio
async def test_local_reranker_promotes_rare_query_terms():
    candidates = [
        {"chunk_uuid": "generic", "snippet": "general AI policy", "score": 0.5},
        {
            "chunk_uuid": "specific",
            "snippet": "NIST AI RMF govern map measure manage",
            "score": 0.5,
        },
    ]
    result = await rerank(
        "NIST AI RMF governance measure", candidates, top_k=2, provider="local"
    )
    assert result[0]["chunk_uuid"] == "specific"


@pytest.mark.asyncio
async def test_local_reranker_can_boost_matching_source_metadata():
    candidates = [
        {
            "chunk_uuid": "generic",
            "filename": "generic-policy.pdf",
            "snippet": "AI governance requirements",
            "score": 0.5,
        },
        {
            "chunk_uuid": "authority",
            "filename": "who-lmm-ethics-governance.pdf",
            "snippet": "AI governance requirements",
            "score": 0.5,
        },
    ]

    result = await rerank(
        "WHO LMM governance",
        candidates,
        top_k=2,
        provider="local",
        metadata_weight=0.2,
    )

    assert result[0]["chunk_uuid"] == "authority"
    assert result[0]["metadata_score"] > result[1]["metadata_score"]


@pytest.mark.asyncio
async def test_local_reranker_supports_stronger_lexical_correction():
    candidates = [
        {
            "chunk_uuid": "semantic",
            "snippet": "general governance considerations",
            "score": 0.9,
        },
        {
            "chunk_uuid": "anchored",
            "snippet": "Regulation EU 2024 1689 high risk systems",
            "score": 0.5,
        },
    ]

    result = await rerank(
        "Regulation EU 2024 1689",
        candidates,
        top_k=2,
        provider="local",
        lexical_weight=0.8,
    )

    assert result[0]["chunk_uuid"] == "anchored"
