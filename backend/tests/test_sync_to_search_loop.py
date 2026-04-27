"""Sprint F Task 2 — sync→search loop integration test.

Sprint B built `connector → ConnectorIndexer → Weaviate → search_documents`
but never wrote a test that exercised the full chain. This file is that test.

Strategy: stand up an in-memory fake Weaviate that round-trips chunks. When
`ConnectorIndexer.index()` calls `store_memory`, the fake captures the
`(properties, vector)` tuple. When `RagRetrievalService.retrieve()` calls
`hybrid_search`, the fake replays everything matching `user_id` (BM25 / cosine
are out of scope — what matters is that the chunk written upstream is
visible downstream).

If this test breaks in the future, the indexer→retrieval contract drifted —
investigate before "fixing" the test.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from services.connectors.base import SourceItem


USER_ID = "11111111-2222-3333-4444-555555555555"


class _FakeWeaviateRoundTrip:
    """In-memory shim with the two methods the chain calls."""

    def __init__(self):
        self._objects: list[dict] = []

    def store_memory(self, collection, content, vector):
        uid = str(uuid4())
        self._objects.append(
            {"uuid": uid, "properties": dict(content), "vector": list(vector)}
        )
        return uid

    def hybrid_search(
        self, collection, query, query_vector, user_id, limit=5, alpha=0.7
    ):
        # Match RagRetrievalService.retrieve()'s shape exactly.
        out = []
        for obj in self._objects:
            if obj["properties"].get("user_id") != str(user_id):
                continue
            out.append(
                {
                    "uuid": obj["uuid"],
                    "properties": obj["properties"],
                    "score": 1.0,
                }
            )
            if len(out) >= limit:
                break
        return out


@pytest.mark.asyncio
async def test_sync_to_search_round_trip():
    """Insert source_item → indexer.index() → retrieve() returns the chunk."""
    from services.connector_indexer import ConnectorIndexer
    from services.rag_retrieval import RagRetrievalService

    fake = _FakeWeaviateRoundTrip()

    item_body = (
        "The Q2 strategy memo flagged Project Atlas as the top retention "
        "initiative for the next two quarters."
    )
    item = SourceItem(
        user_id=USER_ID,
        source_type="gmail",
        source_item_type="email",
        external_id="msg_atlas_001",
        title="Re: Q2 strategy",
        body=item_body,
        item_at="2026-04-20T10:00:00+00:00",
    )

    embed_mock = MagicMock()
    embed_mock.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    embed_mock.generate_query_embedding = AsyncMock(return_value=[0.1] * 768)

    # Patch both the indexer's and rag_retrieval's hooks to point at the
    # same fake Weaviate + the same embedding singleton.
    with patch(
        "services.connector_indexer.get_weaviate_client", return_value=fake
    ), patch(
        "services.connector_indexer.get_embedding_service", return_value=embed_mock
    ), patch(
        "services.rag_retrieval.get_weaviate_client", return_value=fake
    ), patch(
        "services.rag_retrieval._get_embedding_service", return_value=embed_mock
    ):
        n = await ConnectorIndexer().index(item)
        assert n >= 1, "indexer should have written at least one chunk"

        results = await RagRetrievalService().retrieve(
            query="What did we say about Project Atlas?",
            user_id=USER_ID,
            k=5,
        )

    # The chain holds: at least one chunk surfaces and its content matches
    # what we inserted upstream.
    assert len(results) >= 1
    snippet = results[0]["snippet"]
    assert "Project Atlas" in snippet
    assert results[0]["source_type"] == "gmail"
    assert results[0]["filename"] == "Re: Q2 strategy"


@pytest.mark.asyncio
async def test_retrieve_isolates_users():
    """A chunk written under user A must not leak into user B's retrieval."""
    from services.connector_indexer import ConnectorIndexer
    from services.rag_retrieval import RagRetrievalService

    fake = _FakeWeaviateRoundTrip()
    other_user = "99999999-9999-9999-9999-999999999999"

    item = SourceItem(
        user_id=USER_ID,
        source_type="slack",
        source_item_type="message",
        external_id="slack_msg_42",
        title="#engineering",
        body="Deploy is rolling out at 3pm UTC.",
    )

    embed_mock = MagicMock()
    embed_mock.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    embed_mock.generate_query_embedding = AsyncMock(return_value=[0.1] * 768)

    with patch(
        "services.connector_indexer.get_weaviate_client", return_value=fake
    ), patch(
        "services.connector_indexer.get_embedding_service", return_value=embed_mock
    ), patch(
        "services.rag_retrieval.get_weaviate_client", return_value=fake
    ), patch(
        "services.rag_retrieval._get_embedding_service", return_value=embed_mock
    ):
        await ConnectorIndexer().index(item)
        results = await RagRetrievalService().retrieve(
            query="deploy", user_id=other_user, k=5
        )

    assert results == []
