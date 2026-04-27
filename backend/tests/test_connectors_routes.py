"""Sprint B Task 8: `/api/connectors` route tests.

Three smoke tests:
  * GET / lists connectors with the expected shape
  * POST /{source}/backfill calls start_backfill and returns job_id
  * DELETE /{source} calls disconnect_data_source and returns counts
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_user_id, get_current_read_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_app(ingestion_mock, indexer_mock=None):
    """Build a FastAPI app with the connectors router and overridden auth+DI."""
    from routes.connectors import router, get_data_ingestion, get_connector_indexer

    app = FastAPI()
    app.include_router(router, prefix="/api/connectors", tags=["connectors"])
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_data_ingestion] = lambda: ingestion_mock
    if indexer_mock is not None:
        app.dependency_overrides[get_connector_indexer] = lambda: indexer_mock
    return app


def _make_db_mock(per_call_fetchone):
    """Build a get_db_connection mock whose cursor.fetchone() returns each
    value in `per_call_fetchone` in order."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = list(per_call_fetchone)

    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def test_list_connectors_returns_status():
    """GET /api/connectors returns one row per supported source. Gmail is
    connected with 5 items; the other two are absent."""
    last_item_at = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)

    # SUPPORTED order is gmail, slack, google_calendar.
    # For each source: first fetchone => data_sources row, second => stats row.
    per_call = [
        # gmail
        {"oauth_token_encrypted": "tok", "last_sync": last_item_at},
        {"last_item_at": last_item_at, "items_count": 5},
        # slack
        None,
        {"last_item_at": None, "items_count": 0},
        # google_calendar
        None,
        {"last_item_at": None, "items_count": 0},
    ]
    conn, _cursor = _make_db_mock(per_call)

    ingestion_mock = MagicMock()
    app = make_app(ingestion_mock)

    with patch(
        "routes.connectors.get_db_connection", return_value=conn
    ):
        with TestClient(app) as client:
            resp = client.get("/api/connectors")

    assert resp.status_code == 200
    body = resp.json()
    assert "connectors" in body
    rows = {r["source_type"]: r for r in body["connectors"]}
    assert set(rows.keys()) == {"gmail", "slack", "google_calendar"}

    gmail = rows["gmail"]
    assert gmail["connected"] is True
    assert gmail["items_count"] == 5
    assert gmail["last_sync_at"] is not None

    slack = rows["slack"]
    assert slack["connected"] is False
    assert slack["items_count"] == 0
    assert slack["last_sync_at"] is None


def test_backfill_triggers_start_backfill():
    """POST /api/connectors/gmail/backfill invokes start_backfill and surfaces
    the returned job_id with status='complete'."""
    ingestion_mock = MagicMock()
    ingestion_mock.start_backfill = AsyncMock(return_value="job-uuid-123")

    app = make_app(ingestion_mock)

    with TestClient(app) as client:
        resp = client.post(
            "/api/connectors/gmail/backfill",
            json={"since": "2026-01-01T00:00:00+00:00"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"job_id": "job-uuid-123", "status": "complete"}

    ingestion_mock.start_backfill.assert_awaited_once()
    args, kwargs = ingestion_mock.start_backfill.await_args
    assert args[0] == TEST_USER_ID
    assert args[1] == "gmail"
    assert kwargs["since"] == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_backfill_rejects_unsupported_source():
    ingestion_mock = MagicMock()
    ingestion_mock.start_backfill = AsyncMock()
    app = make_app(ingestion_mock)

    with TestClient(app) as client:
        resp = client.post("/api/connectors/notion/backfill", json={})

    assert resp.status_code == 400
    ingestion_mock.start_backfill.assert_not_awaited()


def test_disconnect_calls_disconnect_data_source():
    """DELETE /api/connectors/slack invokes disconnect_data_source and returns
    the cleanup counts."""
    ingestion_mock = MagicMock()
    ingestion_mock.disconnect_data_source = AsyncMock(
        return_value={
            "vectors_deleted": 12,
            "items_deleted": 4,
            "tokens_deleted": 1,
        }
    )

    app = make_app(ingestion_mock)

    with TestClient(app) as client:
        resp = client.delete("/api/connectors/slack")

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"vectors_deleted": 12, "items_deleted": 4, "tokens_deleted": 1}

    ingestion_mock.disconnect_data_source.assert_awaited_once_with(
        TEST_USER_ID, "slack"
    )


# ── Sprint F Task 2: reindex endpoint ────────────────────────────────────


def _reindex_db_mock(stuck_rows):
    """Mock get_db_connection; first cursor.fetchall() returns `stuck_rows`,
    subsequent execute() calls (the per-row UPDATE) are no-ops."""
    cursor = MagicMock()
    cursor.fetchall.return_value = stuck_rows

    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def test_reindex_returns_processed_succeeded_failed():
    """POST /api/connectors/gmail/reindex calls indexer.index for each stuck
    row and returns processed/succeeded/failed counts."""
    stuck = [
        {
            "id": "row-1",
            "user_id": TEST_USER_ID,
            "source_type": "gmail",
            "source_item_type": "email",
            "external_id": "msg_1",
            "title": "subj 1",
            "body": "body 1",
            "metadata": {},
            "item_at": None,
            "embedding_status": "failed",
            "sensitivity": 0,
        },
        {
            "id": "row-2",
            "user_id": TEST_USER_ID,
            "source_type": "gmail",
            "source_item_type": "email",
            "external_id": "msg_2",
            "title": "subj 2",
            "body": "body 2",
            "metadata": {},
            "item_at": None,
            "embedding_status": None,
            "sensitivity": 0,
        },
    ]
    conn, _cur = _reindex_db_mock(stuck)

    indexer_mock = MagicMock()
    # First succeeds, second raises — exercises the failed-counter branch.
    indexer_mock.index = AsyncMock(side_effect=[1, RuntimeError("weaviate down")])

    app = make_app(MagicMock(), indexer_mock=indexer_mock)

    with patch("routes.connectors.get_db_connection", return_value=conn):
        with TestClient(app) as client:
            resp = client.post("/api/connectors/gmail/reindex")

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"processed": 2, "succeeded": 1, "failed": 1}
    assert indexer_mock.index.await_count == 2


def test_reindex_excludes_completed_items():
    """The SQL filter must skip rows where embedding_status='completed'.
    We verify the SELECT contains the filter and that rows the mock returns
    are the only ones the indexer sees."""
    # Mock returns ZERO stuck rows (because all are 'completed' upstream).
    conn, cur = _reindex_db_mock([])

    indexer_mock = MagicMock()
    indexer_mock.index = AsyncMock(return_value=1)

    app = make_app(MagicMock(), indexer_mock=indexer_mock)

    with patch("routes.connectors.get_db_connection", return_value=conn):
        with TestClient(app) as client:
            resp = client.post("/api/connectors/gmail/reindex")

    assert resp.status_code == 200
    assert resp.json() == {"processed": 0, "succeeded": 0, "failed": 0}
    # No items → indexer never called.
    indexer_mock.index.assert_not_awaited()

    # Verify the SQL filters out completed rows.
    select_call = cur.execute.call_args_list[0]
    sql = select_call.args[0]
    assert "embedding_status" in sql
    assert "!= 'completed'" in sql
    assert "LIMIT 200" in sql


def test_reindex_rejects_unsupported_source():
    indexer_mock = MagicMock()
    indexer_mock.index = AsyncMock()
    app = make_app(MagicMock(), indexer_mock=indexer_mock)

    with TestClient(app) as client:
        resp = client.post("/api/connectors/notion/reindex")

    assert resp.status_code == 400
    indexer_mock.index.assert_not_awaited()
