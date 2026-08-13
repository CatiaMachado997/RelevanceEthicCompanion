"""Regression tests for typed chat persistence and atomic conversation storage."""

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from models.context import Goal
from services.context_manager import ContextManager
from services.langchain_tools import (
    GoalCreateTool,
    NoteCreateTool,
    NoteCreateInput,
    TaskCreateTool,
    UserValueCreateInput,
    UserValueCreateTool,
)
from orchestrator.nodes.tools import (
    _clean_persistence_confirmation,
    _enforce_explicit_persistence_intent,
)


@pytest.mark.asyncio
async def test_create_goal_tool_persists_a_real_goal():
    saved = Goal(
        id="goal-123",
        user_id="user-1",
        title="Ship the release",
        created_at=datetime.now(timezone.utc),
    )
    context_manager = AsyncMock()
    context_manager.create_goal.return_value = saved

    result = json.loads(
        await GoalCreateTool(context_manager, "user-1")._arun(
            title="Ship the release", priority=8
        )
    )

    goal = context_manager.create_goal.await_args.args[0]
    assert goal.user_id == "user-1"
    assert goal.title == "Ship the release"
    assert goal.priority == 8
    assert goal.metadata["source"] == "chat_tool"
    assert len(goal.metadata["chat_dedupe_key"]) == 64
    assert result == {
        "status": "saved",
        "kind": "goal",
        "id": "goal-123",
        "title": "Ship the release",
        "duplicate": False,
    }


@pytest.mark.asyncio
async def test_goal_repository_uses_database_dedupe_without_exposing_key():
    created_at = datetime.now(timezone.utc)
    cursor = FakeCursor(
        [{"id": "existing-goal", "created_at": created_at, "inserted": False}]
    )

    @contextmanager
    def fake_connection():
        yield FakeConnection(cursor)

    goal = Goal(
        user_id="user-1",
        title="Wake up at 6am",
        metadata={"source": "chat_tool", "chat_dedupe_key": "stable-key"},
    )
    with patch("services.context_manager.get_db_connection", fake_connection):
        saved = await ContextManager.__new__(ContextManager).create_goal(goal)

    query, params = cursor.executions[0]
    assert "ON CONFLICT (user_id, chat_dedupe_key)" in query
    assert params[-1] == "stable-key"
    assert json.loads(params[-2]) == {"source": "chat_tool"}
    assert saved.id == "existing-goal"
    assert saved.metadata == {"source": "chat_tool", "_duplicate": True}


def test_note_and_value_schemas_cannot_masquerade_as_goals():
    assert "as_goal" not in NoteCreateInput.model_fields
    value_schema = UserValueCreateInput.model_json_schema()
    assert set(value_schema["properties"]["value_type"]["enum"]) == {
        "preference",
        "boundary",
        "topic_filter",
        "time_window",
    }


class FakeCursor:
    def __init__(self, rows=None):
        self.executions = []
        self.rows = iter(
            rows
            or [
                {"id": "user-turn"},
                {"id": "assistant-turn"},
            ]
        )
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return next(self.rows)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        return None


@pytest.mark.asyncio
async def test_conversation_exchange_stores_both_turns_and_updates_title():
    cursor = FakeCursor()

    @contextmanager
    def fake_connection():
        yield FakeConnection(cursor)

    with patch("services.context_manager.get_db_connection", fake_connection):
        result = await ContextManager.__new__(
            ContextManager
        ).store_conversation_exchange(
            user_id="user-1",
            user_content="Plan my launch week",
            assistant_content="## Plan\n\n- Start Monday",
            conversation_id="conversation-1",
            assistant_metadata={"citations": []},
        )

    assert result == {
        "user_turn_id": "user-turn",
        "assistant_turn_id": "assistant-turn",
    }
    assert len(cursor.executions) == 3
    assert "INSERT INTO conversation_turns" in cursor.executions[0][0]
    assert "INSERT INTO conversation_turns" in cursor.executions[1][0]
    assert "UPDATE conversations" in cursor.executions[2][0]
    assert cursor.executions[2][1] == (
        "Plan my launch week",
        "conversation-1",
        "user-1",
    )


@pytest.mark.asyncio
async def test_create_task_tool_uses_task_fields_and_chat_origin():
    cursor = FakeCursor([{"id": "task-1", "title": "Send proposal"}])

    @contextmanager
    def fake_connection():
        yield FakeConnection(cursor)

    with patch("utils.db.get_db_connection", fake_connection):
        result = json.loads(
            await TaskCreateTool("user-1")._arun(
                title="Send proposal", priority=2, goal_id="goal-1"
            )
        )

    assert result["kind"] == "task"
    query, params = cursor.executions[0]
    assert "INSERT INTO tasks" in query
    assert "'chat'" in query
    assert params[:7] == ("user-1", None, "goal-1", "Send proposal", None, 2, None)
    assert len(params[7]) == 64


@pytest.mark.asyncio
async def test_save_user_value_tool_preserves_boundary_type():
    cursor = FakeCursor(
        [{"id": "value-1", "type": "boundary", "value": "No work after 18:00"}]
    )

    @contextmanager
    def fake_connection():
        yield FakeConnection(cursor)

    with patch("utils.db.get_db_connection", fake_connection):
        result = json.loads(
            await UserValueCreateTool("user-1")._arun(
                value="No work after 18:00", value_type="boundary", priority=1
            )
        )

    assert result["kind"] == "value"
    query, params = cursor.executions[0]
    assert "INSERT INTO user_values" in query
    assert params[:4] == ("user-1", "boundary", "No work after 18:00", 1)
    assert len(params[5]) == 64


@pytest.mark.asyncio
async def test_duplicate_note_does_not_duplicate_semantic_memory():
    cursor = FakeCursor([{"id": "note-1", "value": "Remember this", "inserted": False}])
    context_manager = AsyncMock()

    @contextmanager
    def fake_connection():
        yield FakeConnection(cursor)

    with patch("services.langchain_tools.get_db_connection", fake_connection):
        result = json.loads(
            await NoteCreateTool(context_manager, "user-1")._arun("Remember this")
        )

    assert result["duplicate"] is True
    context_manager.store_semantic_memory.assert_not_awaited()


def test_persistence_confirmation_hides_ids_and_internal_fields():
    result = _clean_persistence_confirmation(
        [
            {
                "tool": "save_user_value",
                "result": json.dumps(
                    {
                        "status": "saved",
                        "kind": "value",
                        "id": "private-id",
                        "value": "I respect privacy",
                    }
                ),
            }
        ]
    )

    assert result == "Saved value in **Values**: “I respect privacy”."
    assert "private-id" not in result
    assert "kind" not in result


def test_persistence_confirmation_deduplicates_replayed_result():
    saved = {
        "tool": "create_goal",
        "result": json.dumps(
            {
                "status": "saved",
                "kind": "goal",
                "id": "goal-1",
                "title": "Wake up at 6am",
            }
        ),
    }

    assert _clean_persistence_confirmation([saved, saved]) == (
        "Created goal in **Goals**: “Wake up at 6am”."
    )


def test_persistence_confirmation_marks_database_duplicate():
    saved = {
        "tool": "create_task",
        "result": json.dumps(
            {
                "status": "saved",
                "kind": "task",
                "id": "task-1",
                "title": "Send proposal",
                "duplicate": True,
            }
        ),
    }

    assert _clean_persistence_confirmation([saved]) == (
        "Already saved in **Tasks**: “Send proposal”."
    )


def test_explicit_goal_request_cannot_be_saved_as_task():
    parsed = {
        "thought": "Save it.",
        "actions": [
            {
                "tool": "create_task",
                "params": {"title": "Dinner at 7pm", "due_date": "2026-08-12T19:00:00"},
            }
        ],
        "raw_tool_calls": [
            {
                "name": "create_task",
                "args": {"title": "Dinner at 7pm", "due_date": "2026-08-12T19:00:00"},
                "id": "call-1",
            }
        ],
    }

    corrected = _enforce_explicit_persistence_intent(
        "creater a goal dinner at 7pm", parsed
    )

    assert corrected["actions"] == [
        {
            "tool": "create_goal",
            "params": {
                "title": "Dinner at 7pm",
                "target_date": "2026-08-12T19:00:00",
            },
        }
    ]
    assert corrected["raw_tool_calls"][0]["name"] == "create_goal"
