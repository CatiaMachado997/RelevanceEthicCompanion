import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.connectors.base import SourceItem


USER_ID = "00000000-0000-0000-0000-000000000000"


def _item(body: str, source_type: str = "gmail", external_id: str = "msg_1") -> SourceItem:
    return SourceItem(
        user_id=USER_ID,
        source_type=source_type,
        source_item_type="email",
        external_id=external_id,
        title="Re: Q2 roadmap",
        body=body,
        item_at="2026-04-20T10:00:00+00:00",
    )


@pytest.mark.asyncio
@patch("services.connector_indexer.get_weaviate_client")
@patch("services.connector_indexer.get_embedding_service")
async def test_short_item_indexes_one_chunk(mock_embed, mock_weaviate):
    from services.connector_indexer import ConnectorIndexer

    weav = MagicMock()
    weav.store_memory = MagicMock()
    mock_weaviate.return_value = weav
    embed = MagicMock()
    embed.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    mock_embed.return_value = embed

    indexer = ConnectorIndexer()
    n = await indexer.index(_item("Short body, fits one chunk."))

    assert n == 1
    assert weav.store_memory.call_count == 1
    args = weav.store_memory.call_args
    assert args[0][0] == "DocumentMemory"
    props = args[0][1]
    assert props["source_type"] == "gmail"
    assert props["chunk_index"] == 0
    assert props["chunk_count"] == 1


@pytest.mark.asyncio
@patch("services.connector_indexer.get_weaviate_client")
@patch("services.connector_indexer.get_embedding_service")
async def test_long_item_splits_into_multiple_chunks(mock_embed, mock_weaviate):
    from services.connector_indexer import ConnectorIndexer

    weav = MagicMock()
    weav.store_memory = MagicMock()
    mock_weaviate.return_value = weav
    embed = MagicMock()
    embed.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    mock_embed.return_value = embed

    long_body = ("Sentence about the roadmap. " * 200)
    indexer = ConnectorIndexer()
    n = await indexer.index(_item(long_body))

    assert n > 1
    assert weav.store_memory.call_count == n


@pytest.mark.asyncio
@patch("services.connector_indexer.get_weaviate_client")
async def test_returns_zero_when_weaviate_unavailable(mock_weaviate):
    from services.connector_indexer import ConnectorIndexer
    mock_weaviate.return_value = None
    indexer = ConnectorIndexer()
    n = await indexer.index(_item("anything"))
    assert n == 0


@pytest.mark.asyncio
@patch("services.connector_indexer.get_weaviate_client")
@patch("services.connector_indexer.get_embedding_service")
async def test_empty_body_is_skipped(mock_embed, mock_weaviate):
    from services.connector_indexer import ConnectorIndexer
    weav = MagicMock()
    mock_weaviate.return_value = weav
    embed = MagicMock()
    embed.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    mock_embed.return_value = embed

    indexer = ConnectorIndexer()
    n = await indexer.index(_item(""))
    assert n == 0
    weav.store_memory.assert_not_called()
