"""Tests that critical DB tables exist and have expected columns."""
import pytest
from utils.db import get_db_connection


def test_source_items_table_exists():
    """source_items table must exist with required columns."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'source_items'
                ORDER BY ordinal_position
            """)
            cols = [r['column_name'] for r in cur.fetchall()]
    required = {'id', 'user_id', 'source_type', 'source_item_type',
                'external_id', 'title', 'body', 'metadata', 'item_at', 'synced_at',
                'embedding_status', 'sensitivity', 'relevance_hints'}
    assert required.issubset(set(cols)), f"Missing columns: {required - set(cols)}"
