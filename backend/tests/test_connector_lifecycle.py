"""Sprint B Task 6: Disconnect cleanup tests.

Verifies that disconnecting a connector wipes Weaviate vectors, source_items
rows, and the data_sources row in the correct order (vectors first, SQL
second — so SQL state still drives retries on partial failure).
"""

import pytest
from unittest.mock import MagicMock, patch


USER_ID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.asyncio
@patch("services.data_ingestion.get_db_connection")
@patch("services.data_ingestion.get_weaviate_client")
async def test_disconnect_removes_tokens_items_and_vectors(mock_weav, mock_db):
    from services.data_ingestion import DataIngestionService

    weav = MagicMock()
    weav.delete_by_filter = MagicMock(return_value=42)
    mock_weav.return_value = weav

    cur = MagicMock()
    cur.rowcount = 7
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    mock_db.return_value.__enter__.return_value = conn

    svc = DataIngestionService(MagicMock())
    result = await svc.disconnect_data_source(USER_ID, "gmail")

    # Vectors first, then SQL
    weav.delete_by_filter.assert_called_once_with(
        "DocumentMemory",
        {"user_id": USER_ID, "source_type": "gmail"},
    )
    # Two DELETE statements: source_items then data_sources
    assert cur.execute.call_count >= 2
    executed_sql = " ".join(str(call.args[0]) for call in cur.execute.call_args_list)
    assert "DELETE FROM source_items" in executed_sql
    assert "DELETE FROM data_sources" in executed_sql

    assert result["vectors_deleted"] == 42
    assert result["items_deleted"] == 7
    assert result["tokens_deleted"] == 7
    conn.commit.assert_called_once()
