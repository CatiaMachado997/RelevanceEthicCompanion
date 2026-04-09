"""Tests that the auth session cookie is set with correct security attributes."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_secure_cookie(monkeypatch):
    """TestClient with COOKIE_SECURE=True."""
    with patch("utils.weaviate_client.get_weaviate_client", return_value=None):
        from main import app
        from config import settings
        monkeypatch.setattr(settings, "COOKIE_SECURE", True)
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


@pytest.fixture
def client_with_insecure_cookie(monkeypatch):
    """TestClient with COOKIE_SECURE=False (default dev setting)."""
    with patch("utils.weaviate_client.get_weaviate_client", return_value=None):
        from main import app
        from config import settings
        monkeypatch.setattr(settings, "COOKIE_SECURE", False)
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


def test_session_cookie_samesite_strict(client_with_insecure_cookie):
    """Session cookie always has SameSite=Strict."""
    resp = client_with_insecure_cookie.post(
        "/api/auth/session",
        json={"access_token": "fake-token", "remember_me": False},
    )
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "samesite=strict" in set_cookie.lower()


def test_session_cookie_secure_flag_when_enabled(client_with_secure_cookie):
    """Cookie has Secure flag when COOKIE_SECURE=True."""
    resp = client_with_secure_cookie.post(
        "/api/auth/session",
        json={"access_token": "fake-token", "remember_me": False},
    )
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "secure" in set_cookie.lower()


def test_session_cookie_no_secure_in_dev(client_with_insecure_cookie):
    """Cookie does NOT have Secure flag in dev (COOKIE_SECURE=False)."""
    resp = client_with_insecure_cookie.post(
        "/api/auth/session",
        json={"access_token": "fake-token", "remember_me": False},
    )
    set_cookie = resp.headers.get("set-cookie", "")
    # FastAPI omits "secure" attribute when secure=False
    assert "samesite=strict" in set_cookie.lower()
