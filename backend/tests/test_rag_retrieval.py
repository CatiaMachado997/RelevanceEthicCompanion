"""Tests for RagRetrievalService — hybrid search over DocumentMemory."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


USER_ID = "00000000-0000-0000-0000-000000000000"


def _make_weaviate_mock(results=None):
    """Return a mock weaviate client whose hybrid_search returns `results`."""
    client = MagicMock()
    client.hybrid_search = MagicMock(return_value=results or [])
    return client


def _make_embedder_mock(vector=None):
    """Return a mock EmbeddingService with async generate_query_embedding."""
    embedder = MagicMock()
    embedder.generate_query_embedding = AsyncMock(return_value=vector or [0.1, 0.2])
    return embedder


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_weaviate_unavailable():
    """If get_weaviate_client() returns None, retrieve() returns []."""
    with patch(
        "services.rag_retrieval.get_weaviate_client", return_value=None
    ), patch(
        "services.rag_retrieval._get_embedding_service",
        return_value=_make_embedder_mock(),
    ):
        from services.rag_retrieval import RagRetrievalService

        results = await RagRetrievalService().retrieve("hello", USER_ID)

    assert results == []


@pytest.mark.asyncio
async def test_retrieve_formats_hybrid_search_results():
    """Each Weaviate result is mapped into the citation shape."""
    raw = [
        {
            "uuid": "uuid-1",
            "score": 0.91,
            "properties": {
                "content": "The answer is 42.",
                "document_id": "doc-1",
                "filename": "answers.md",
                "chunk_index": 3,
            },
        }
    ]
    weaviate = _make_weaviate_mock(raw)
    with patch(
        "services.rag_retrieval.get_weaviate_client", return_value=weaviate
    ), patch(
        "services.rag_retrieval._get_embedding_service",
        return_value=_make_embedder_mock(vector=[0.5, 0.6]),
    ):
        from services.rag_retrieval import RagRetrievalService

        results = await RagRetrievalService().retrieve("what is the answer?", USER_ID)

    assert len(results) == 1
    r = results[0]
    assert r["chunk_uuid"] == "uuid-1"
    assert r["document_id"] == "doc-1"
    assert r["filename"] == "answers.md"
    assert r["chunk_index"] == 3
    assert r["snippet"] == "The answer is 42."
    assert r["score"] == 0.91
    # Sprint B Task 9: legacy uploaded docs default to "document".
    assert r["source_type"] == "document"


@pytest.mark.asyncio
async def test_retrieve_surfaces_source_type_for_connector_content():
    """Sprint B Task 9: connector chunks expose their source_type ("gmail"/"slack")."""
    raw = [
        {
            "uuid": "uuid-gmail-1",
            "score": 0.88,
            "properties": {
                "content": "Q2 roadmap discussion thread.",
                "document_id": "gmail:abc123",
                "filename": "Re: Q2 roadmap",
                "chunk_index": 0,
                "source_type": "gmail",
            },
        },
        {
            "uuid": "uuid-slack-1",
            "score": 0.77,
            "properties": {
                "content": "Deploy went green on friday.",
                "document_id": "slack:xyz789",
                "filename": "#engineering",
                "chunk_index": 0,
                "source_type": "slack",
            },
        },
    ]
    weaviate = _make_weaviate_mock(raw)
    with patch(
        "services.rag_retrieval.get_weaviate_client", return_value=weaviate
    ), patch(
        "services.rag_retrieval._get_embedding_service",
        return_value=_make_embedder_mock(vector=[0.5, 0.6]),
    ):
        from services.rag_retrieval import RagRetrievalService

        results = await RagRetrievalService().retrieve("Q2 roadmap", USER_ID)

    assert len(results) == 2
    assert results[0]["source_type"] == "gmail"
    assert results[1]["source_type"] == "slack"


@pytest.mark.asyncio
async def test_retrieve_passes_user_id_and_query_to_hybrid_search():
    """User ID isolation: hybrid_search is called with the caller's user_id."""
    weaviate = _make_weaviate_mock([])
    with patch(
        "services.rag_retrieval.get_weaviate_client", return_value=weaviate
    ), patch(
        "services.rag_retrieval._get_embedding_service",
        return_value=_make_embedder_mock(vector=[0.7]),
    ):
        from services.rag_retrieval import RagRetrievalService

        await RagRetrievalService().retrieve("policies", USER_ID, k=5)

    weaviate.hybrid_search.assert_called_once()
    kwargs = weaviate.hybrid_search.call_args.kwargs
    assert kwargs["collection"] == "DocumentMemory"
    assert kwargs["user_id"] == USER_ID
    assert kwargs["query"] == "policies"
    assert kwargs["query_vector"] == [0.7]
    # Sprint G Task 3: hybrid search now pulls a wider pool (floor 20) so the
    # cross-encoder reranker has meaningful candidates; rerank trims back to k.
    assert kwargs["limit"] == 20
    # 2026 best practice: alpha=0.7 favors dense vector but keeps BM25 contribution
    assert kwargs["alpha"] == 0.7


@pytest.mark.asyncio
async def test_retrieve_with_trace_builds_trace_no_rerank():
    """Sprint G Task 4: trace mirrors hybrid candidates and final cited UUIDs.

    With JINA_API_KEY empty (default in tests), rerank falls back and the
    `rerank_applied` flag must be False with `rerank_top=None`.
    """
    raw = [
        {
            "uuid": "uuid-1",
            "score": 0.91,
            "properties": {
                "content": "The answer is 42.",
                "document_id": "doc-1",
                "filename": "answers.md",
                "chunk_index": 3,
            },
        },
        {
            "uuid": "uuid-2",
            "score": 0.55,
            "properties": {
                "content": "Unrelated content.",
                "document_id": "doc-2",
                "filename": "other.md",
                "chunk_index": 0,
            },
        },
    ]
    weaviate = _make_weaviate_mock(raw)
    with patch(
        "services.rag_retrieval.get_weaviate_client", return_value=weaviate
    ), patch(
        "services.rag_retrieval._get_embedding_service",
        return_value=_make_embedder_mock(vector=[0.5, 0.6]),
    ):
        from services.rag_retrieval import RagRetrievalService

        results, trace = await RagRetrievalService().retrieve_with_trace(
            "what is the answer?", USER_ID, k=2
        )

    assert trace["query"] == "what is the answer?"
    assert len(trace["candidates"]) == 2
    assert trace["candidates"][0]["chunk_uuid"] == "uuid-1"
    assert trace["candidates"][0]["hybrid_score"] == 0.91
    assert "answer is 42" in trace["candidates"][0]["snippet_preview"]
    assert trace["rerank_applied"] is False
    assert trace["rerank_top"] is None
    assert trace["final"] == [r["chunk_uuid"] for r in results]


@pytest.mark.asyncio
async def test_retrieve_with_trace_marks_rerank_applied():
    """When rerank annotates results with `rerank_score`, trace.rerank_applied
    flips to True and `rerank_top` lists the (chunk_uuid, rerank_score) pairs."""
    raw = [
        {
            "uuid": "uuid-a",
            "score": 0.5,
            "properties": {
                "content": "alpha",
                "document_id": "d",
                "filename": "f",
                "chunk_index": 0,
            },
        }
    ]
    weaviate = _make_weaviate_mock(raw)
    with patch(
        "services.rag_retrieval.get_weaviate_client", return_value=weaviate
    ), patch(
        "services.rag_retrieval._get_embedding_service",
        return_value=_make_embedder_mock(vector=[0.1]),
    ), patch(
        "services.rag_retrieval.rerank",
        AsyncMock(
            return_value=[
                {
                    "chunk_uuid": "uuid-a",
                    "filename": "f",
                    "snippet": "alpha",
                    "score": 0.5,
                    "rerank_score": 0.97,
                    "source_type": "document",
                }
            ]
        ),
    ):
        from services.rag_retrieval import RagRetrievalService

        results, trace = await RagRetrievalService().retrieve_with_trace(
            "alpha?", USER_ID, k=1
        )

    assert len(results) == 1
    assert trace["rerank_applied"] is True
    assert trace["rerank_top"] == [{"chunk_uuid": "uuid-a", "rerank_score": 0.97}]
    assert trace["final"] == ["uuid-a"]


@pytest.mark.asyncio
async def test_retrieve_with_trace_returns_empty_trace_when_weaviate_unavailable():
    """Trace is always built — even when retrieval short-circuits."""
    with patch(
        "services.rag_retrieval.get_weaviate_client", return_value=None
    ), patch(
        "services.rag_retrieval._get_embedding_service",
        return_value=_make_embedder_mock(),
    ):
        from services.rag_retrieval import RagRetrievalService

        results, trace = await RagRetrievalService().retrieve_with_trace(
            "hi", USER_ID
        )

    assert results == []
    assert trace["query"] == "hi"
    assert trace["candidates"] == []
    assert trace["rerank_applied"] is False
    assert trace["rerank_top"] is None
    assert trace["final"] == []


@pytest.mark.asyncio
async def test_retrieve_returns_empty_on_weaviate_error():
    """If hybrid_search raises, retrieve() degrades to [] (don't break the chat turn)."""
    weaviate = MagicMock()
    weaviate.hybrid_search = MagicMock(side_effect=RuntimeError("Weaviate down"))
    with patch(
        "services.rag_retrieval.get_weaviate_client", return_value=weaviate
    ), patch(
        "services.rag_retrieval._get_embedding_service",
        return_value=_make_embedder_mock(),
    ):
        from services.rag_retrieval import RagRetrievalService

        results = await RagRetrievalService().retrieve("anything", USER_ID)

    assert results == []
