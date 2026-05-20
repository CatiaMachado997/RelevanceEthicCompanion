"""Sprint F Task 6: GET /api/today/feed."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_read_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def _make_app():
    from routes.today import router

    app = FastAPI()
    app.include_router(router, prefix="/api/today")
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return app


def _mock_db_router(query_router):
    """Build a get_db_connection mock that picks rows by inspecting SQL.

    `query_router(sql, params) -> list[dict]` chooses what fetchall() returns.
    """
    state: dict = {"pending": []}
    cur = MagicMock()

    def execute(sql, params=()):
        state["pending"] = query_router(sql, params)

    cur.execute.side_effect = execute
    cur.fetchall.side_effect = lambda: state["pending"]

    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


def test_today_feed_shape_with_one_row_per_category():
    """Mock returns one row per category — assert response shape and serialization."""
    now = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)

    task_due = {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Ship Sprint F",
        "status": "in_progress",
        "priority": 3,
        "due_date": now,
        "project_id": None,
    }
    task_overdue = {
        "id": "22222222-2222-2222-2222-222222222222",
        "title": "Old thing",
        "status": "todo",
        "priority": 5,
        "due_date": now,
        "project_id": None,
    }
    gmail_row = {
        "id": "33333333-3333-3333-3333-333333333333",
        "title": "Re: launch plan",
        "body": "Ack — looks good. We can ship Friday.",
        "metadata": {"url": "https://mail.google.com/mail/u/0/#inbox/abc"},
        "item_at": now,
        "synced_at": now,
        "external_id": "gmail-abc",
    }
    slack_row = {
        "id": "44444444-4444-4444-4444-444444444444",
        "title": "#general",
        "body": "Heads up: standup at 10",
        "metadata": {"permalink": "https://slack.com/archives/CXX/p123"},
        "item_at": now,
        "synced_at": now,
        "external_id": "slack-msg-1",
    }
    cal_row = {
        "id": "55555555-5555-5555-5555-555555555555",
        "title": "Sprint review",
        "body": "",
        "metadata": {},
        "item_at": now,
        "synced_at": now,
        "external_id": "cal-evt-1",
    }

    def route(sql: str, params):
        s = " ".join(sql.split())
        if "FROM tasks" in s and "due_date <" in s:
            return [task_overdue]
        if "FROM tasks" in s:
            return [task_due]
        if "source_type = 'google_calendar'" in s or (
            "source_type" in s and "google_calendar" in str(params)
        ):
            return [cal_row]
        if "FROM source_items" in s and params and "gmail" in params:
            return [gmail_row]
        if "FROM source_items" in s and params and "slack" in params:
            return [slack_row]
        return []

    with patch("routes.today.get_db_connection") as mock_db:
        mock_db.side_effect = lambda: _mock_db_router(route)

        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/today/feed")

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == {
        "tasks_due_today",
        "tasks_overdue",
        "recent_emails",
        "recent_slack",
        "calendar_today",
    }

    assert len(body["tasks_due_today"]) == 1
    assert body["tasks_due_today"][0]["title"] == "Ship Sprint F"
    assert body["tasks_due_today"][0]["id"] == str(task_due["id"])

    assert len(body["tasks_overdue"]) == 1
    assert body["tasks_overdue"][0]["title"] == "Old thing"

    assert len(body["recent_emails"]) == 1
    em = body["recent_emails"][0]
    assert em["title"] == "Re: launch plan"
    assert em["snippet"].startswith("Ack")
    assert em["url"] == "https://mail.google.com/mail/u/0/#inbox/abc"
    assert em["source_ref"] == "gmail-abc"

    assert len(body["recent_slack"]) == 1
    sl = body["recent_slack"][0]
    assert sl["url"] == "https://slack.com/archives/CXX/p123"

    assert len(body["calendar_today"]) == 1
    assert body["calendar_today"][0]["title"] == "Sprint review"


def test_today_feed_all_empty():
    """No data anywhere — all five lists empty, status 200."""
    with patch("routes.today.get_db_connection") as mock_db:
        mock_db.side_effect = lambda: _mock_db_router(lambda *_: [])

        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/today/feed")

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "tasks_due_today": [],
        "tasks_overdue": [],
        "recent_emails": [],
        "recent_slack": [],
        "calendar_today": [],
    }
