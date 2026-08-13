"""Tests for durable saved-item card state."""

import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from routes.chat import SavedItemUndo, mark_saved_item_undone


class Cursor:
    def __init__(self, row):
        self.row = row
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor


@pytest.mark.asyncio
async def test_mark_saved_item_undone_updates_owned_assistant_turn():
    cursor = Cursor(
        {
            "metadata": {
                "saved_items": [
                    {
                        "id": "goal-1",
                        "kind": "goal",
                        "label": "Ship release",
                        "destination": "Goals",
                        "duplicate": False,
                    }
                ]
            }
        }
    )

    @contextmanager
    def connection():
        yield Connection(cursor)

    with patch("routes.chat.get_db_connection", connection):
        result = await mark_saved_item_undone(
            "assistant-turn",
            SavedItemUndo(kind="goal", item_id="goal-1"),
            user_id="user-1",
        )

    assert result == {"success": True}
    select_query, select_params = cursor.executions[0]
    assert "user_id = %s" in select_query
    assert select_params == ("assistant-turn", "user-1")
    update_query, update_params = cursor.executions[1]
    assert "UPDATE conversation_turns" in update_query
    assert json.loads(update_params[0])["saved_items"][0]["undone"] is True
