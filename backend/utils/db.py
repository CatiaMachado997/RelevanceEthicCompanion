"""
PostgreSQL connection management — psycopg3 pool.

A singleton ConnectionPool is opened during FastAPI lifespan (main.py calls
open_pool() on startup, close_pool() on shutdown). All DB access checks out a
connection from the pool instead of opening a new TCP connection per request.

Usage:
    from utils.db import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config import settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def open_pool() -> None:
    """Create the connection pool. Call once in FastAPI lifespan startup."""
    global _pool
    if _pool is not None:
        return
    _pool = ConnectionPool(
        conninfo=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=True,
    )
    logger.info("PostgreSQL connection pool opened (min=2, max=10)")


def close_pool() -> None:
    """Close the connection pool. Call once in FastAPI lifespan shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("PostgreSQL connection pool closed")


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """Check out a connection from the pool; auto-commit or rollback on exit.

    Falls back to a direct connection if the pool has not been opened yet
    (useful in tests and management scripts that don't run the full lifespan).
    """
    global _pool
    if _pool is None:
        logger.debug("Pool not open — opening direct connection")
        conn = psycopg.connect(settings.DATABASE_URL, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return

    with _pool.connection() as conn:
        yield conn


def get_db():
    return get_db_connection()
