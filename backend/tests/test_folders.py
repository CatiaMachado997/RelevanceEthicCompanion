"""
Folders Route Integration Tests

Pattern borrowed from test_goals_routes.py:
- Build a minimal FastAPI app with just the folders router
- Override auth dependencies to a fixed TEST_USER_ID
- Mock routes.folders.get_db_connection
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, UTC
import pytest

from routes.folders import router as folders_router
from utils.supabase_auth import get_current_user_id, get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"
OTHER_USER_ID = "11111111-1111-1111-1111-111111111111"


def make_app():
    app = FastAPI()
    app.include_router(folders_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


def make_db_mock(fetchone_result=None, fetchall_result=None, rowcount=1):
    """Build a mock for get_db_connection() context manager."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result
    mock_cursor.fetchall.return_value = fetchall_result or []
    mock_cursor.rowcount = rowcount

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


SAMPLE_FOLDER_ROW = {
    "id": "folder-001",
    "name": "Work",
    "color": "#4a7c59",
    "position": 0,
    "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
}


# ─── GET /api/folders ──────────────────────────────────────────────────


def test_list_folders_empty(client):
    mock_conn, _ = make_db_mock(fetchall_result=[])
    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.get("/api/folders")
    assert r.status_code == 200
    assert r.json() == {"folders": []}


def test_list_folders_returns_rows(client):
    mock_conn, _ = make_db_mock(fetchall_result=[SAMPLE_FOLDER_ROW])
    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.get("/api/folders")
    assert r.status_code == 200
    body = r.json()
    assert len(body["folders"]) == 1
    assert body["folders"][0]["name"] == "Work"
    assert body["folders"][0]["color"] == "#4a7c59"


# ─── POST /api/folders ─────────────────────────────────────────────────


def test_create_folder_success(client):
    # First execute() is the MAX(position) query returning next_pos = 0,
    # second is the INSERT returning the created row.
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [{"next_pos": 0}, SAMPLE_FOLDER_ROW]
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.post("/api/folders", json={"name": "Work", "color": "#4a7c59"})

    assert r.status_code == 200
    assert r.json()["name"] == "Work"
    assert r.json()["position"] == 0


def test_create_folder_duplicate_name_returns_409(client):
    """Creating a folder with the same name as an existing one should 409."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [{"next_pos": 0}, SAMPLE_FOLDER_ROW]
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    # Arrange: simulate psycopg's UniqueViolation on INSERT. The MAX query
    # completes normally; the INSERT raises.
    from psycopg.errors import UniqueViolation

    def execute_side_effect(sql, params=None):
        if "INSERT INTO folders" in sql:
            raise UniqueViolation("duplicate key value violates unique constraint")
        return None

    mock_cursor.execute.side_effect = execute_side_effect

    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.post("/api/folders", json={"name": "Work"})

    assert r.status_code == 409
    assert "already exists" in r.json()["detail"].lower()


def test_create_folder_rejects_empty_name(client):
    r = client.post("/api/folders", json={"name": ""})
    assert r.status_code == 422  # Pydantic validation


def test_create_folder_rejects_overlong_name(client):
    r = client.post("/api/folders", json={"name": "x" * 81})
    assert r.status_code == 422


# ─── PATCH /api/folders/{id} ───────────────────────────────────────────


def test_update_folder_rename(client):
    updated = dict(SAMPLE_FOLDER_ROW)
    updated["name"] = "Personal"
    mock_conn, _ = make_db_mock(fetchone_result=updated)

    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.patch("/api/folders/folder-001", json={"name": "Personal"})
    assert r.status_code == 200
    assert r.json()["name"] == "Personal"


def test_update_folder_not_found(client):
    mock_conn, _ = make_db_mock(fetchone_result=None)
    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.patch("/api/folders/nonexistent", json={"name": "X"})
    assert r.status_code == 404


def test_update_folder_requires_a_field(client):
    r = client.patch("/api/folders/folder-001", json={})
    assert r.status_code == 400
    assert "No fields to update" in r.json()["detail"]


def test_update_folder_duplicate_name_returns_409(client):
    """PATCH that renames a folder to an existing name returns 409."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    from psycopg.errors import UniqueViolation

    def execute_side_effect(sql, params=None):
        if "UPDATE folders" in sql:
            raise UniqueViolation("duplicate key value violates unique constraint")
        return None

    mock_cursor.execute.side_effect = execute_side_effect

    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.patch("/api/folders/folder-001", json={"name": "Work"})

    assert r.status_code == 409
    assert "already exists" in r.json()["detail"].lower()


# ─── DELETE /api/folders/{id} ──────────────────────────────────────────


def test_delete_folder_success(client):
    mock_conn, _ = make_db_mock(rowcount=1)
    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.delete("/api/folders/folder-001")
    assert r.status_code == 200
    assert r.json() == {"success": True}


def test_delete_folder_not_found(client):
    mock_conn, _ = make_db_mock(rowcount=0)
    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.delete("/api/folders/missing")
    assert r.status_code == 404


# ─── PATCH /api/folders/conversations/{id} ─────────────────────────────


def test_move_conversation_into_folder(client):
    # First fetchone(): folder-exists check → returns {"?column?": 1}
    # Second fetchone(): UPDATE ... RETURNING → row
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [
        (1,),
        {"id": "conv-001", "folder_id": "folder-001"},
    ]
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.patch(
            "/api/folders/conversations/conv-001",
            json={"folder_id": "folder-001"},
        )
    assert r.status_code == 200
    assert r.json() == {"id": "conv-001", "folder_id": "folder-001"}


def test_move_conversation_out_of_folder(client):
    # When folder_id is null, the folder-exists check is skipped entirely.
    mock_conn, _ = make_db_mock(
        fetchone_result={"id": "conv-001", "folder_id": None},
    )
    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.patch(
            "/api/folders/conversations/conv-001",
            json={"folder_id": None},
        )
    assert r.status_code == 200
    assert r.json() == {"id": "conv-001", "folder_id": None}


def test_move_conversation_to_unowned_folder(client):
    # The folder-exists check returns None → 404.
    mock_conn, _ = make_db_mock(fetchone_result=None)
    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.patch(
            "/api/folders/conversations/conv-001",
            json={"folder_id": "someone-elses-folder"},
        )
    assert r.status_code == 404
    assert "Target folder" in r.json()["detail"]


def test_move_nonexistent_conversation(client):
    mock_cursor = MagicMock()
    # folder-exists check passes, but UPDATE ... RETURNING yields None
    mock_cursor.fetchone.side_effect = [(1,), None]
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.patch(
            "/api/folders/conversations/missing",
            json={"folder_id": "folder-001"},
        )
    assert r.status_code == 404
    assert "Conversation not found" in r.json()["detail"]
