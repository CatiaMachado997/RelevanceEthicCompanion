"""Tests for seed_dev idempotency."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


def _make_mock_conn(existing_email: str | None = None):
    """Return a mock connection that reports whether the dev user exists."""
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = (
        {"id": "test-uuid-1234", "email": existing_email} if existing_email else None
    )
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    return mock_conn, mock_cur


class TestSeedDev:
    def test_seed_creates_user_when_not_exists(self):
        mock_conn, mock_cur = _make_mock_conn(existing_email=None)
        mock_cur.fetchone.side_effect = [
            None,
            {"id": "new-uuid", "email": "dev@ethic-companion.local"},
        ]

        with patch("scripts.seed_dev.get_db_connection", return_value=mock_conn):
            from scripts.seed_dev import seed

            seed()

        execute_calls = " ".join(
            c.args[0] for c in mock_cur.execute.call_args_list if c.args
        )
        assert "INSERT" in execute_calls

    def test_seed_skips_user_insert_when_exists(self):
        mock_conn, mock_cur = _make_mock_conn(
            existing_email="dev@ethic-companion.local"
        )

        with patch("scripts.seed_dev.get_db_connection", return_value=mock_conn):
            from scripts.seed_dev import seed

            seed()

        execute_calls = " ".join(
            c.args[0] for c in mock_cur.execute.call_args_list if c.args
        )
        assert "INSERT INTO public.users" not in execute_calls

    def test_seed_is_idempotent(self):
        mock_conn, mock_cur = _make_mock_conn(
            existing_email="dev@ethic-companion.local"
        )

        with patch("scripts.seed_dev.get_db_connection", return_value=mock_conn):
            from scripts.seed_dev import seed

            seed()
            seed()
