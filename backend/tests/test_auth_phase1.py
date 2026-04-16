from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from config import settings
from routes.auth import router as auth_router
from routes.chat import router as chat_router
from routes.data_sources import router as data_sources_router, get_data_ingestion
from routes.values import router as values_router
from routes.goals import router as goals_router
from utils.oauth_state import create_signed_state, validate_signed_state


class FakeIngestion:
    async def initiate_oauth(
        self, user_id: str, source_type: str, oauth_state: str = ""
    ):
        return f"https://oauth.example/{source_type}?state={oauth_state}"

    async def sync_data_source(self, user_id: str, source_type: str):
        return {
            "success": True,
            "message": "ok",
            "items_synced": 1,
            "source_type": source_type,
        }

    async def disconnect_source(self, user_id: str, source_type: str):
        return True

    async def handle_oauth_callback(
        self, source_type: str, authorization_code: str, user_id: str
    ):
        return {"success": True, "message": "ok", "source_type": source_type}


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(data_sources_router)
    app.include_router(values_router)
    app.include_router(goals_router)
    app.dependency_overrides[get_data_ingestion] = lambda: FakeIngestion()

    monkeypatch.setattr(settings, "AUTH_ENFORCEMENT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_ENFORCE_WRITE_ROUTES", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")

    return TestClient(app)


def test_auth_me_requires_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_auth_me_uses_dev_fallback_when_enforcement_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENFORCEMENT_ENABLED", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["user_id"] == "00000000-0000-0000-0000-000000000000"


def test_auth_me_accepts_valid_token(client, monkeypatch):
    monkeypatch.setattr(
        "utils.supabase_auth._decode_supabase_token",
        lambda token: {"sub": "user-123", "email": "u@example.com"},
    )
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["user_id"] == "user-123"


def test_chat_write_route_requires_auth(client):
    response = client.post("/api/chat/", json={"message": "hello"})
    assert response.status_code == 401


def test_chat_history_read_route_requires_auth_when_read_enforced(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENFORCE_READ_ROUTES", True)
    response = client.get("/api/chat/history")
    assert response.status_code == 401


def test_chat_history_read_route_allows_dev_fallback_when_read_not_enforced(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "AUTH_ENFORCEMENT_ENABLED", False)
    monkeypatch.setattr(settings, "AUTH_ENFORCE_READ_ROUTES", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    response = client.get("/api/chat/history")
    assert response.status_code == 200


def test_data_source_sync_requires_auth(client):
    response = client.post("/api/data-sources/sync/google_calendar")
    assert response.status_code == 401


def test_values_write_route_requires_auth(client):
    response = client.post(
        "/api/values/",
        json={"type": "boundary", "value": "no_work_after_19h", "priority": 1},
    )
    assert response.status_code == 401


def test_goals_write_route_requires_auth(client):
    response = client.post("/api/goals/", json={"title": "Test Goal", "priority": 1})
    assert response.status_code == 401


def test_data_source_sync_with_auth(client, monkeypatch):
    monkeypatch.setattr(
        "utils.supabase_auth._decode_supabase_token",
        lambda token: {"sub": "user-123", "email": "u@example.com"},
    )
    response = client.post(
        "/api/data-sources/sync/google_calendar",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_oauth_state_roundtrip():
    state = create_signed_state(user_id="user-abc", source_type="google_calendar")
    user_id = validate_signed_state(state=state, expected_source_type="google_calendar")
    assert user_id == "user-abc"


def test_oauth_state_replay_rejected():
    state = create_signed_state(user_id="user-abc", source_type="google_calendar")
    validate_signed_state(state=state, expected_source_type="google_calendar")
    with pytest.raises(Exception):
        validate_signed_state(state=state, expected_source_type="google_calendar")
