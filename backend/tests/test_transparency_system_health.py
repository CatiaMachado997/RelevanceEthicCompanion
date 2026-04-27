"""Sprint E Task 3: GET /api/transparency/system-health."""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_read_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_app(health_mock):
    from routes.transparency import router, get_system_health_service

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_system_health_service] = lambda: health_mock
    return app


def test_get_system_health_returns_aggregated_shape():
    health = MagicMock()
    health.get_tool_health.return_value = [
        {
            "tool_name": "search_documents",
            "source": "chat",
            "calls_24h": 12,
            "success_rate": 1.0,
            "p50_latency_ms": 45,
            "p95_latency_ms": 120,
        }
    ]
    health.get_esl_summary.return_value = {
        "APPROVED": {"count_24h": 10, "count_7d": 80},
        "VETOED": {"count_24h": 1, "count_7d": 3},
    }
    health.get_scheduler_status.return_value = [
        {
            "job_id": "relevance_scan",
            "next_run_time": "2026-04-26T13:00:00+00:00",
            "trigger": "interval[0:15:00]",
        }
    ]
    app = make_app(health)

    with TestClient(app) as client:
        resp = client.get("/api/transparency/system-health")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert set(data.keys()) == {"tool_health", "esl_summary", "scheduler"}

    assert data["tool_health"][0]["tool_name"] == "search_documents"
    assert data["tool_health"][0]["calls_24h"] == 12
    assert data["tool_health"][0]["p95_latency_ms"] == 120

    assert data["esl_summary"]["APPROVED"]["count_24h"] == 10
    assert data["esl_summary"]["VETOED"]["count_7d"] == 3

    assert data["scheduler"][0]["job_id"] == "relevance_scan"
    assert data["scheduler"][0]["next_run_time"].startswith("2026-04-26T13:00:00")

    health.get_tool_health.assert_called_once_with(TEST_USER_ID)
    health.get_esl_summary.assert_called_once_with(TEST_USER_ID)
    health.get_scheduler_status.assert_called_once_with()
