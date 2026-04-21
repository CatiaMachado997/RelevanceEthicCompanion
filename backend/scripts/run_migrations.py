"""
SQL Migration Runner

Applies pending .sql files from the migrations/ directory in alphabetical order.
Tracks applied migrations in a `schema_migrations` table to ensure idempotency.

Usage:
    python -m scripts.run_migrations
    python -m scripts.run_migrations --migrations-dir /path/to/migrations
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def get_db_connection():
    from utils.db import get_db_connection as _get

    return _get()


def run_migrations(migrations_dir: str | None = None) -> None:
    """Apply all pending .sql files in migrations_dir."""
    if migrations_dir is None:
        migrations_dir = str(Path(__file__).parent.parent / "migrations")

    sql_files = sorted(f for f in os.listdir(migrations_dir) if f.endswith(".sql"))

    if not sql_files:
        logger.info("No migration files found in %s", migrations_dir)
        return

    # Ensure the tracking table exists and get already-applied set.
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename   TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

    # Each migration runs in its own connection so it commits atomically.
    # If a migration fails, only that migration is rolled back; earlier ones
    # already committed and will not be re-run.
    for filename in sql_files:
        if filename in applied:
            logger.info("  skip (already applied): %s", filename)
            continue

        filepath = os.path.join(migrations_dir, filename)
        sql = Path(filepath).read_text(encoding="utf-8")

        logger.info("  applying: %s", filename)
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (filename) VALUES (%s)",
                        (filename,),
                    )
        except Exception:
            logger.exception("  failed while applying: %s", filename)
            raise
        logger.info("  done: %s", filename)

    logger.info("Migrations complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Run pending SQL migrations")
    parser.add_argument("--migrations-dir", default=None)
    args = parser.parse_args()
    try:
        run_migrations(migrations_dir=args.migrations_dir)
    except Exception:
        # The inner per-file handler already logged filename + full traceback.
        sys.exit(1)
