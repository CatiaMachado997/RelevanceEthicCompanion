"""Sprint C Task 8: GET /api/transparency/tool-calls."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_read_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def _sample_row():
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "user_id": TEST_USER_ID,
        "tool_name": "search_documents",
        "source": "chat",
        "source_ref": "conv-abc",
        "input": {"query": "hello"},
        "output": {"chunks": []},
        "status": "success",
        "error_message": None,
        "esl_decision": "APPROVED",
        "latency_ms": 42,
        "created_at": datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc),
    }


def make_app(telemetry_mock):
    from routes.transparency import router, get_tool_telemetry_service

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_tool_telemetry_service] = lambda: telemetry_mock
    return app


def test_list_tool_calls_default():
    telemetry = MagicMock()
    telemetry.list_tool_calls.return_value = [_sample_row()]
    app = make_app(telemetry)

    with TestClient(app) as client:
        resp = client.get("/api/transparency/tool-calls")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "events" in data
    assert len(data["events"]) == 1
    event = data["events"][0]
    assert event["tool_name"] == "search_documents"
    assert event["source"] == "chat"
    assert event["status"] == "success"
    assert event["esl_decision"] == "APPROVED"
    assert event["latency_ms"] == 42
    assert event["created_at"].startswith("2026-04-26T12:00:00")
    telemetry.list_tool_calls.assert_called_once_with(
        TEST_USER_ID,
        tool_name=None,
        source=None,
        since=None,
        limit=50,
    )


def test_list_tool_calls_invalid_since_returns_400():
    telemetry = MagicMock()
    app = make_app(telemetry)

    with TestClient(app) as client:
        resp = client.get("/api/transparency/tool-calls?since=garbage")

    assert resp.status_code == 400
    telemetry.list_tool_calls.assert_not_called()


def test_list_tool_calls_passes_filters_to_service():
    telemetry = MagicMock()
    telemetry.list_tool_calls.return_value = []
    app = make_app(telemetry)

    with TestClient(app) as client:
        resp = client.get(
            "/api/transparency/tool-calls"
            "?tool_name=search_documents&source=scheduled&limit=10"
        )

    assert resp.status_code == 200, resp.text
    telemetry.list_tool_calls.assert_called_once_with(
        TEST_USER_ID,
        tool_name="search_documents",
        source="scheduled",
        since=None,
        limit=10,
    )


def test_list_tool_calls_caps_limit_at_200():
    telemetry = MagicMock()
    telemetry.list_tool_calls.return_value = []
    app = make_app(telemetry)

    with TestClient(app) as client:
        resp = client.get("/api/transparency/tool-calls?limit=999")

    assert resp.status_code == 200, resp.text
    _, kwargs = telemetry.list_tool_calls.call_args
    assert kwargs["limit"] == 200
