"""Sprint B Task 7: Backfill job tracking tests.

Verifies that DataIngestionService.start_backfill correctly drives the
connector_backfill_jobs lifecycle (pending -> running -> complete|failed).
"""

import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


USER_ID = "00000000-0000-0000-0000-000000000000"
JOB_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _setup_mock_db(mock_db):
    """Wire up a MagicMock cursor that returns JOB_ID on RETURNING id fetch."""
    cur = MagicMock()
    cur.fetchone.return_value = {"id": JOB_ID}
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    mock_db.return_value.__enter__.return_value = conn
    return cur, conn


@pytest.mark.asyncio
@patch("services.data_ingestion.get_db_connection")
async def test_start_backfill_success(mock_db):
    from services.data_ingestion import DataIngestionService

    cur, conn = _setup_mock_db(mock_db)

    svc = DataIngestionService(MagicMock())
    svc.sync_data_source = AsyncMock(
        return_value={"success": True, "items_synced": 12, "source_type": "gmail"}
    )

    result = await svc.start_backfill(USER_ID, "gmail")

    # Returned UUID is a string
    assert isinstance(result, str)
    assert result == str(JOB_ID)

    # sync_data_source was called with since=None
    svc.sync_data_source.assert_awaited_once_with(USER_ID, "gmail", since=None)

    # Inspect SQL statements executed in order
    sqls = [str(call.args[0]) for call in cur.execute.call_args_list]
    joined = " | ".join(sqls)

    # 1. INSERT as pending
    assert any(
        "INSERT INTO connector_backfill_jobs" in s and "'pending'" in s for s in sqls
    ), f"missing pending INSERT in: {joined}"
    # 2. UPDATE to running
    assert any(
        "UPDATE connector_backfill_jobs" in s and "'running'" in s for s in sqls
    ), f"missing running UPDATE in: {joined}"
    # 3. UPDATE to complete with items_processed
    assert any(
        "UPDATE connector_backfill_jobs" in s
        and "'complete'" in s
        and "items_processed" in s
        for s in sqls
    ), f"missing complete UPDATE in: {joined}"

    # items_processed = 12 was passed in the complete UPDATE
    complete_call = next(
        c for c in cur.execute.call_args_list if "'complete'" in str(c.args[0])
    )
    assert 12 in complete_call.args[1]


@pytest.mark.asyncio
@patch("services.data_ingestion.get_db_connection")
async def test_start_backfill_failure(mock_db):
    from services.data_ingestion import DataIngestionService

    cur, conn = _setup_mock_db(mock_db)

    svc = DataIngestionService(MagicMock())
    svc.sync_data_source = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await svc.start_backfill(USER_ID, "slack")

    sqls = [str(call.args[0]) for call in cur.execute.call_args_list]
    joined = " | ".join(sqls)

    # Pending INSERT and running UPDATE still happened
    assert any(
        "INSERT INTO connector_backfill_jobs" in s and "'pending'" in s for s in sqls
    ), f"missing pending INSERT in: {joined}"
    assert any(
        "UPDATE connector_backfill_jobs" in s and "'running'" in s for s in sqls
    ), f"missing running UPDATE in: {joined}"
    # Failed UPDATE recorded
    assert any(
        "UPDATE connector_backfill_jobs" in s and "'failed'" in s for s in sqls
    ), f"missing failed UPDATE in: {joined}"

    # error_message contains "boom"
    failed_call = next(
        c for c in cur.execute.call_args_list if "'failed'" in str(c.args[0])
    )
    assert any("boom" in str(p) for p in failed_call.args[1])
