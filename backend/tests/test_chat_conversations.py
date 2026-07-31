"""
Tests for GET /api/chat/conversations/{conversation_id}

Pattern mirrors test_folders.py:
- Build a minimal FastAPI app with just the chat router
- Override auth dependency to a fixed TEST_USER_ID
- Mock routes.chat.get_db_connection
"""

from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime, UTC

from utils.supabase_auth import get_current_user_id, get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"
CONVERSATION_ID = "22222222-2222-2222-2222-222222222222"


def _make_app_and_client():
    from routes.chat import router as chat_router

    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return TestClient(app)


def _db_mock(fetchone=None):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


def test_get_conversation_returns_row():
    client = _make_app_and_client()
    row = {
        "id": CONVERSATION_ID,
        "title": "Hello",
        "folder_id": None,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 2, tzinfo=UTC),
    }
    with patch("routes.chat.get_db_connection", return_value=_db_mock(fetchone=row)):
        r = client.get(f"/api/chat/conversations/{CONVERSATION_ID}")
    assert r.status_code == 200
    assert r.json()["title"] == "Hello"
    assert r.json()["folder_id"] is None


def test_get_conversation_404():
    client = _make_app_and_client()
    with patch("routes.chat.get_db_connection", return_value=_db_mock(fetchone=None)):
        r = client.get(f"/api/chat/conversations/{CONVERSATION_ID}")
    assert r.status_code == 404


def test_get_conversation_rejects_invalid_uuid():
    client = _make_app_and_client()
    r = client.get("/api/chat/conversations/not-a-uuid")
    assert r.status_code == 422


def test_stream_rejects_invalid_conversation_uuid():
    client = _make_app_and_client()
    r = client.get(
        "/api/chat/stream",
        params={"message": "hello", "conversation_id": "not-a-uuid"},
    )
    assert r.status_code == 422


def test_stream_rejects_conversation_owned_by_another_user():
    client = _make_app_and_client()
    with patch("routes.chat.get_db_connection", return_value=_db_mock(fetchone=None)):
        r = client.get(
            "/api/chat/stream",
            params={"message": "hello", "conversation_id": CONVERSATION_ID},
        )
    assert r.status_code == 404


def test_delete_conversation_not_found():
    client = _make_app_and_client()
    conn = _db_mock()
    conn.cursor.return_value.__enter__.return_value.rowcount = 0
    with patch("routes.chat.get_db_connection", return_value=conn):
        r = client.delete(f"/api/chat/conversations/{CONVERSATION_ID}")
    assert r.status_code == 404


def test_create_conversation_uses_supplied_title():
    client = _make_app_and_client()
    row = {
        "id": CONVERSATION_ID,
        "title": "Plan the launch",
        "folder_id": None,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    conn = _db_mock(fetchone=row)
    with patch("routes.chat.get_db_connection", return_value=conn):
        r = client.post(
            "/api/chat/conversations", json={"title": "Plan the launch"}
        )
    assert r.status_code == 200
    assert r.json()["title"] == "Plan the launch"
