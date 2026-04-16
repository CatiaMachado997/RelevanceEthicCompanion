"""Tests for auth_audit.py logger."""

import time
from unittest.mock import MagicMock, patch


def test_log_auth_event_inserts_row():
    """log_auth_event fires an INSERT without blocking the caller."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("utils.auth_audit.get_db_connection", return_value=mock_conn):
        from utils.auth_audit import _write_audit_event

        _write_audit_event(
            event="login_success",
            user_id="user-123",
            ip_address="127.0.0.1",
            user_agent="pytest",
            detail=None,
        )

    mock_cur.execute.assert_called_once()
    call_args = mock_cur.execute.call_args[0]
    assert "INSERT INTO auth_audit_log" in call_args[0]
    assert "login_success" in call_args[1]


def test_log_auth_event_does_not_raise_on_db_error():
    """A DB failure in the audit logger must NOT propagate to the caller."""
    with patch("utils.auth_audit.get_db_connection", side_effect=Exception("DB down")):
        from utils import auth_audit

        # Should not raise
        auth_audit._write_audit_event(
            event="login_success",
            user_id=None,
            ip_address=None,
            user_agent=None,
            detail=None,
        )


def test_log_auth_event_public_api_is_fire_and_forget():
    """log_auth_event is non-blocking (returns immediately, schedules work)."""
    events_written = []

    def fake_write(**kwargs):
        events_written.append(kwargs["event"])

    with patch("utils.auth_audit._write_audit_event", side_effect=fake_write):
        from utils.auth_audit import log_auth_event

        log_auth_event(event="logout", user_id="u1")
        # Give the background thread time to run
        time.sleep(0.05)

    assert "logout" in events_written
