import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from services.data_ingestion import DataIngestionService, TokenExpiredError
from services.context_manager import ContextManager


def _make_svc():
    return DataIngestionService(MagicMock(spec=ContextManager))


def _db_mock(row):
    """Return a mock context manager for get_db_connection that yields `row` from fetchone()."""
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = row
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cur


@pytest.mark.asyncio
async def test_valid_token_returned_without_refresh():
    """Token not expired — returned immediately, no refresh call made."""
    svc = _make_svc()
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    row = {
        "oauth_token_encrypted": "valid_token",
        "oauth_refresh_token_encrypted": "refresh_tok",
        "token_expires_at": future,
    }
    mock_conn, _ = _db_mock(row)
    with patch(
        "services.data_ingestion.get_db_connection", return_value=mock_conn
    ), patch("services.data_ingestion.Credentials") as mock_creds_cls:
        token = await svc._get_valid_token("user1", "google_calendar")
    assert token == "valid_token"
    mock_creds_cls.assert_not_called()


@pytest.mark.asyncio
async def test_expired_token_triggers_refresh():
    """Expired token — Google returns new token and DB is updated."""
    svc = _make_svc()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    row = {
        "oauth_token_encrypted": "old_token",
        "oauth_refresh_token_encrypted": "refresh_tok",
        "token_expires_at": past,
    }
    mock_conn, mock_cur = _db_mock(row)
    mock_creds = MagicMock()
    mock_creds.token = "new_access_token"
    mock_creds.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    with patch(
        "services.data_ingestion.get_db_connection", return_value=mock_conn
    ), patch("services.data_ingestion.Credentials", return_value=mock_creds), patch(
        "services.data_ingestion.Request"
    ):
        token = await svc._get_valid_token("user1", "google_calendar")
    assert token == "new_access_token"
    execute_calls = " ".join(str(c) for c in mock_cur.execute.call_args_list)
    assert "UPDATE" in execute_calls


@pytest.mark.asyncio
async def test_refresh_failure_disables_source():
    """Refresh fails (invalid_grant) — source disabled, TokenExpiredError raised."""
    svc = _make_svc()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    row = {
        "oauth_token_encrypted": "old_token",
        "oauth_refresh_token_encrypted": "bad_refresh",
        "token_expires_at": past,
    }
    mock_conn, mock_cur = _db_mock(row)
    mock_creds = MagicMock()
    mock_creds.refresh.side_effect = Exception("invalid_grant")
    with patch(
        "services.data_ingestion.get_db_connection", return_value=mock_conn
    ), patch("services.data_ingestion.Credentials", return_value=mock_creds), patch(
        "services.data_ingestion.Request"
    ):
        with pytest.raises(TokenExpiredError):
            await svc._get_valid_token("user1", "google_calendar")
    execute_calls = " ".join(str(c) for c in mock_cur.execute.call_args_list)
    assert "enabled = FALSE" in execute_calls


@pytest.mark.asyncio
async def test_missing_refresh_token_raises_error():
    """No refresh token stored — raises TokenExpiredError immediately, no network call."""
    svc = _make_svc()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    row = {
        "oauth_token_encrypted": "old_token",
        "oauth_refresh_token_encrypted": None,
        "token_expires_at": past,
    }
    mock_conn, _ = _db_mock(row)
    with patch(
        "services.data_ingestion.get_db_connection", return_value=mock_conn
    ), patch("services.data_ingestion.Credentials") as mock_creds_cls:
        with pytest.raises(TokenExpiredError):
            await svc._get_valid_token("user1", "google_calendar")
    mock_creds_cls.assert_not_called()
