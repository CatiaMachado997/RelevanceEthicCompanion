"""Tests for run_migrations dry-run flag."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_migration_files(tmp_path: Path, filenames: list[str]) -> str:
    for name in filenames:
        (tmp_path / name).write_text(f"-- {name}\nSELECT 1;")
    return str(tmp_path)


def _make_mock_conn(applied: set[str]):
    """Return a mock psycopg connection whose cursor reports `applied` as done."""
    mock_rows = [{"filename": f} for f in applied]
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchall.return_value = mock_rows
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    return mock_conn, mock_cur


class TestDryRunMigrations:
    def test_dry_run_returns_pending_filenames(self, tmp_path):
        migrations_dir = _make_migration_files(
            tmp_path, ["001_init.sql", "002_users.sql"]
        )
        mock_conn, mock_cur = _make_mock_conn({"001_init.sql"})

        with patch(
            "scripts.run_migrations.get_db_connection", return_value=mock_conn
        ):
            from scripts.run_migrations import dry_run_migrations

            pending = dry_run_migrations(migrations_dir=migrations_dir)

        assert pending == [("002_users.sql", "-- 002_users.sql\nSELECT 1;")]

    def test_dry_run_does_not_apply_migrations(self, tmp_path):
        migrations_dir = _make_migration_files(tmp_path, ["001_init.sql"])
        mock_conn, mock_cur = _make_mock_conn(set())

        with patch(
            "scripts.run_migrations.get_db_connection", return_value=mock_conn
        ):
            from scripts.run_migrations import dry_run_migrations

            dry_run_migrations(migrations_dir=migrations_dir)

        # cursor.execute should only have been called for the tracking-table
        # setup and SELECT — never for the migration SQL itself
        execute_calls = mock_cur.execute.call_args_list
        called_sqls = [c.args[0] for c in execute_calls if c.args]
        assert not any("SELECT 1" in s for s in called_sqls)

    def test_dry_run_all_applied_returns_empty(self, tmp_path):
        migrations_dir = _make_migration_files(tmp_path, ["001_init.sql"])
        mock_conn, _ = _make_mock_conn({"001_init.sql"})

        with patch(
            "scripts.run_migrations.get_db_connection", return_value=mock_conn
        ):
            from scripts.run_migrations import dry_run_migrations

            pending = dry_run_migrations(migrations_dir=migrations_dir)

        assert pending == []
