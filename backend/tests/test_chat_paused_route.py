import os
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _client():
    os.environ.setdefault("COMPOSIO_CACHE_DIR", "/tmp/relevance-composio-cache")
    from main import app
    from routes.chat import get_current_read_user_id

    app.dependency_overrides[get_current_read_user_id] = lambda: "user-1"
    return TestClient(app), app


def test_paused_route_recovers_interrupt_payload():
    client, app = _client()
    db = MagicMock()
    db.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = {
        "?column?": 1
    }
    interrupt = MagicMock(value={"tool": "create_note", "step": 1, "action_index": 0})
    task = MagicMock(interrupts=(interrupt,))
    graph = MagicMock()
    graph.aget_state = AsyncMock(return_value=MagicMock(tasks=(task,)))
    try:
        with patch("routes.chat.get_db_connection", return_value=db), patch(
            "orchestrator.graph.get_graph_async", AsyncMock(return_value=graph)
        ):
            response = client.get("/api/chat/paused/conv-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "paused": True,
        "thread_id": "conv-1",
        "tool": "create_note",
        "step": 1,
        "action_index": 0,
    }
