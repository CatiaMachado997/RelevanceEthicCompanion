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
    assert kwargs["limit"] == 5
    # 2026 best practice: alpha=0.7 favors dense vector but keeps BM25 contribution
    assert kwargs["alpha"] == 0.7


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
