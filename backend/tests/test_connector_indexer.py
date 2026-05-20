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


# ---------------------------------------------------------------------------
# Sprint F Task 1: index-failure observability
# ---------------------------------------------------------------------------


def _mock_db(cur: MagicMock):
    """Build a get_db_connection() context manager that yields a conn whose
    cursor() context manager yields ``cur``. Mirrors test_task_dependencies."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    db_ctx = MagicMock()
    db_ctx.__enter__.return_value = conn
    db_ctx.__exit__.return_value = False
    return db_ctx, conn


@pytest.mark.asyncio
@patch("services.connector_indexer.get_db_connection")
@patch("services.tool_telemetry.get_db_connection")
@patch("services.connector_indexer.get_weaviate_client")
@patch("services.connector_indexer.get_embedding_service")
async def test_index_failure_marks_row_failed(
    mock_embed, mock_weaviate, mock_telemetry_db, mock_indexer_db
):
    """When the Weaviate write raises, the source_items row is UPDATEd to
    embedding_status='failed' with the exception message in embedding_error,
    and a tool_call_events row is recorded via telemetry."""
    from services.connector_indexer import ConnectorIndexer

    weav = MagicMock()
    weav.store_memory = MagicMock(side_effect=RuntimeError("weaviate down"))
    mock_weaviate.return_value = weav

    embed = MagicMock()
    embed.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    mock_embed.return_value = embed

    indexer_cur = MagicMock()
    indexer_db_ctx, _ = _mock_db(indexer_cur)
    mock_indexer_db.return_value = indexer_db_ctx

    telemetry_cur = MagicMock()
    telemetry_cur.fetchone.return_value = {"id": "evt-1"}
    telemetry_db_ctx, _ = _mock_db(telemetry_cur)
    mock_telemetry_db.return_value = telemetry_db_ctx

    indexer = ConnectorIndexer()
    with pytest.raises(RuntimeError, match="weaviate down"):
        await indexer.index(_item("Some body that produces a chunk."))

    # Row UPDATE: status=failed, error contains the exception message.
    update_calls = [
        c for c in indexer_cur.execute.call_args_list
        if "UPDATE source_items" in c.args[0]
    ]
    assert len(update_calls) == 1
    sql, params = update_calls[0].args
    assert "embedding_status = 'failed'" in sql
    assert "embedding_error" in sql
    err_msg, user_id, source_type, external_id = params
    assert "weaviate down" in err_msg
    assert source_type == "gmail"
    assert external_id == "msg_1"

    # Telemetry insert into tool_call_events.
    telemetry_calls = [
        c for c in telemetry_cur.execute.call_args_list
        if "INSERT INTO tool_call_events" in c.args[0]
    ]
    assert len(telemetry_calls) == 1
    tele_params = telemetry_calls[0].args[1]
    # _INSERT_SQL ordering: user_id, tool_name, source, source_ref, input,
    # output, status, error_message, esl_decision, latency_ms
    assert tele_params[1] == "connector_indexer"
    assert tele_params[2] == "scheduled"
    assert tele_params[3] == "gmail"
    assert tele_params[6] == "error"
    assert "weaviate down" in tele_params[7]


@pytest.mark.asyncio
@patch("services.connector_indexer.get_db_connection")
@patch("services.connector_indexer.get_weaviate_client")
@patch("services.connector_indexer.get_embedding_service")
async def test_index_success_does_not_touch_row(
    mock_embed, mock_weaviate, mock_indexer_db
):
    """On success the indexer no longer writes the row itself — the
    success update lives in data_ingestion._maybe_embed (status='indexed',
    embedding_error=NULL). This test pins that behavior so we don't
    accidentally re-add a duplicate UPDATE here."""
    from services.connector_indexer import ConnectorIndexer

    weav = MagicMock()
    weav.store_memory = MagicMock()
    mock_weaviate.return_value = weav

    embed = MagicMock()
    embed.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    mock_embed.return_value = embed

    indexer_cur = MagicMock()
    indexer_db_ctx, _ = _mock_db(indexer_cur)
    mock_indexer_db.return_value = indexer_db_ctx

    indexer = ConnectorIndexer()
    n = await indexer.index(_item("Short body."))
    assert n == 1
    # No UPDATE on the success path — get_db_connection is not invoked.
    mock_indexer_db.assert_not_called()


@pytest.mark.asyncio
@patch("services.data_ingestion.get_db_connection")
async def test_maybe_embed_success_clears_error(mock_get_db):
    """data_ingestion._maybe_embed writes embedding_status='indexed' and
    embedding_error=NULL after a successful indexer.index() call."""
    from services.data_ingestion import DataIngestionService
    from services.connectors.base import SourceItem

    cur = MagicMock()
    db_ctx, conn = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    item = SourceItem(
        user_id=USER_ID,
        source_type="gmail",
        source_item_type="email",
        external_id="msg_42",
        title="Hello",
        body="world",
        item_at="2026-04-20T10:00:00+00:00",
    )

    svc = DataIngestionService(context_manager=MagicMock())
    with patch("services.data_ingestion.ConnectorIndexer") as IndexerCls:
        inst = IndexerCls.return_value
        inst.index = AsyncMock(return_value=1)
        await svc._maybe_embed(item, USER_ID)

    update_calls = [
        c for c in cur.execute.call_args_list
        if "UPDATE source_items" in c.args[0]
    ]
    assert len(update_calls) == 1
    sql, params = update_calls[0].args
    assert "embedding_status = 'indexed'" in sql
    assert "embedding_error = NULL" in sql
    assert params == (USER_ID, "gmail", "msg_42")
    conn.commit.assert_called_once()
