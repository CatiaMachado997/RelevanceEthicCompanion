"""Sprint J Task 9: integration tests for /api/settings/safety/* routes."""

from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_user_id, get_current_read_user_id


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def _make_app():
    from routes.safety_preferences import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return app


def test_get_safety_returns_shape():
    """GET /api/settings/safety returns master + categories + tools + available_tools."""
    app = _make_app()
    fake_prefs = MagicMock()
    fake_prefs.safe_mode_enabled = False
    fake_prefs.categories = {"write-external"}
    fake_prefs.tools = {"create_note"}

    with patch(
        "routes.safety_preferences.SafetyPreferencesService"
    ) as MockSvc, patch(
        "routes.safety_preferences._list_available_tools",
        return_value=[
            {"name": "query_calendar", "category": "read-personal"},
            {"name": "create_note",    "category": "write-personal"},
        ],
    ):
        MockSvc.return_value.load_for_user.return_value = fake_prefs
        client = TestClient(app)
        r = client.get("/api/settings/safety")

    assert r.status_code == 200
    body = r.json()
    assert body["safe_mode_enabled"] is False
    assert "write-external" in body["categories"]
    assert "create_note" in body["tools"]
    assert isinstance(body["available_tools"], list)
    assert body["available_tools"][0]["category"] == "read-personal"


def test_put_safe_mode_toggles():
    app = _make_app()
    with patch("routes.safety_preferences.SafetyPreferencesService") as MockSvc:
        client = TestClient(app)
        r = client.put("/api/settings/safety/safe-mode", json={"enabled": True})
    assert r.status_code == 200
    MockSvc.return_value.set_safe_mode.assert_called_once_with(
        TEST_USER_ID, enabled=True
    )


def test_put_category_upserts():
    app = _make_app()
    with patch("routes.safety_preferences.SafetyPreferencesService") as MockSvc:
        client = TestClient(app)
        r = client.put(
            "/api/settings/safety/categories/write-external",
            json={"requires_confirmation": True},
        )
    assert r.status_code == 200
    MockSvc.return_value.set_category.assert_called_once_with(
        TEST_USER_ID, category="write-external", requires_confirmation=True
    )


def test_put_category_unknown_returns_422():
    app = _make_app()
    with patch("routes.safety_preferences.SafetyPreferencesService"):
        client = TestClient(app)
        r = client.put(
            "/api/settings/safety/categories/banana",
            json={"requires_confirmation": True},
        )
    assert r.status_code in (400, 422)


def test_put_tool_upserts():
    app = _make_app()
    with patch("routes.safety_preferences.SafetyPreferencesService") as MockSvc:
        client = TestClient(app)
        r = client.put(
            "/api/settings/safety/tools/web_search",
            json={"requires_confirmation": True},
        )
    assert r.status_code == 200
    MockSvc.return_value.set_tool.assert_called_once_with(
        TEST_USER_ID, tool_name="web_search", requires_confirmation=True
    )
