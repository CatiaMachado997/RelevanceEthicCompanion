"""Sprint D Task 6: GET /api/weekly-review."""

from datetime import date
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_read_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


_SAMPLE_RESULT = {
    "period": {"start": "2026-04-20T00:00:00+00:00", "end": "2026-04-27T00:00:00+00:00"},
    "completed_tasks": [],
    "completed_milestones": [],
    "carry_over_tasks": [],
    "upcoming_tasks": [],
    "upcoming_milestones": [],
}


def make_app(rollups_mock):
    from routes.weekly_review import router, get_work_rollups_service

    app = FastAPI()
    app.include_router(router, prefix="/api/weekly-review")
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_work_rollups_service] = lambda: rollups_mock
    return app


def test_get_weekly_review_default_week_start():
    rollups = MagicMock()
    rollups.get_weekly_review.return_value = _SAMPLE_RESULT
    app = make_app(rollups)

    with TestClient(app) as client:
        resp = client.get("/api/weekly-review")

    assert resp.status_code == 200, resp.text
    assert resp.json() == _SAMPLE_RESULT
    rollups.get_weekly_review.assert_called_once_with(TEST_USER_ID, week_start=None)


def test_get_weekly_review_with_week_start():
    rollups = MagicMock()
    rollups.get_weekly_review.return_value = _SAMPLE_RESULT
    app = make_app(rollups)

    with TestClient(app) as client:
        resp = client.get("/api/weekly-review?week_start=2026-04-20")

    assert resp.status_code == 200, resp.text
    assert resp.json() == _SAMPLE_RESULT
    rollups.get_weekly_review.assert_called_once_with(
        TEST_USER_ID, week_start=date(2026, 4, 20)
    )


def test_get_weekly_review_invalid_date_returns_400():
    rollups = MagicMock()
    app = make_app(rollups)

    with TestClient(app) as client:
        resp = client.get("/api/weekly-review?week_start=garbage")

    assert resp.status_code == 400
    rollups.get_weekly_review.assert_not_called()
