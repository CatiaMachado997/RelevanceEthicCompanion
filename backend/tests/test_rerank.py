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
async def test_rerank_falls_back_without_key():
    """Empty api_key → return candidates[:top_k] unchanged, no HTTP call."""
    cands = _candidates(4)

    with patch("services.rerank.httpx.AsyncClient") as client_cls:
        result = await rerank("anything", cands, top_k=3, api_key="")

    # No HTTP client should have been constructed.
    client_cls.assert_not_called()
    # Same objects, in original order, no rerank_score.
    assert len(result) == 3
    assert [r["chunk_uuid"] for r in result] == ["u-0", "u-1", "u-2"]
    for r in result:
        assert "rerank_score" not in r


@pytest.mark.asyncio
async def test_rerank_falls_back_on_http_error():
    """If the Jina call raises, fall back to raw top-K (no rerank_score)."""
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
        assert "rerank_score" not in r


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
        result = await rerank(
            "what is the answer", cands, top_k=5, api_key="fake-key"
        )

    assert [r["chunk_uuid"] for r in result] == ["u-2", "u-0"]
    assert result[0]["rerank_score"] == 0.95
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
