"""Tests for the SQL migration runner script."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cur = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = []  # no migrations applied yet
    return conn, cur


@pytest.fixture
def migrations_dir(tmp_path):
    (tmp_path / "001_create_users.sql").write_text(
        "CREATE TABLE users (id UUID PRIMARY KEY);"
    )
    (tmp_path / "002_add_email.sql").write_text(
        "ALTER TABLE users ADD COLUMN email TEXT;"
    )
    return tmp_path


def test_run_migrations_applies_pending_files(mock_conn, migrations_dir):
    conn, cur = mock_conn
    with patch("scripts.run_migrations.get_db_connection", return_value=conn):
        from scripts.run_migrations import run_migrations

        run_migrations(migrations_dir=str(migrations_dir))

    executed_sqls = [str(c) for c in cur.execute.call_args_list]
    assert any("schema_migrations" in s for s in executed_sqls)
    assert any("CREATE TABLE users" in s for s in executed_sqls)
    assert any("ALTER TABLE users" in s for s in executed_sqls)


def test_run_migrations_skips_already_applied(mock_conn, migrations_dir):
    conn, cur = mock_conn
    cur.fetchall.return_value = [("001_create_users.sql",)]
    with patch("scripts.run_migrations.get_db_connection", return_value=conn):
        from scripts.run_migrations import run_migrations

        run_migrations(migrations_dir=str(migrations_dir))

    executed_sqls = [str(c) for c in cur.execute.call_args_list]
    assert not any(
        "CREATE TABLE users" in s for s in executed_sqls
    ), "001 was already applied and must be skipped"
    assert any(
        "ALTER TABLE users" in s for s in executed_sqls
    ), "002 is pending and must be run"


def test_run_migrations_is_idempotent(mock_conn, migrations_dir):
    conn, cur = mock_conn
    cur.fetchall.return_value = [
        ("001_create_users.sql",),
        ("002_add_email.sql",),
    ]
    with patch("scripts.run_migrations.get_db_connection", return_value=conn):
        from scripts.run_migrations import run_migrations

        run_migrations(migrations_dir=str(migrations_dir))

    executed_sqls = [str(c) for c in cur.execute.call_args_list]
    assert not any("CREATE TABLE users" in s for s in executed_sqls)
    assert not any("ALTER TABLE users" in s for s in executed_sqls)
