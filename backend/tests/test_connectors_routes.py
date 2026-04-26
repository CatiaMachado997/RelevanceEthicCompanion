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


def make_app(ingestion_mock):
    """Build a FastAPI app with the connectors router and overridden auth+DI."""
    from routes.connectors import router, get_data_ingestion

    app = FastAPI()
    app.include_router(router, prefix="/api/connectors", tags=["connectors"])
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_data_ingestion] = lambda: ingestion_mock
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
