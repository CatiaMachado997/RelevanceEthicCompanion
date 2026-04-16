"""Tests for the typed error hierarchy and FastAPI handler."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.errors import (
    IntegrationError,
    DBError,
    AuthError,
    ESLError,
    register_error_handlers,
)


@pytest.fixture
def app_with_handlers():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/integration-error")
    def raise_integration():
        raise IntegrationError("Composio is down")

    @app.get("/db-error")
    def raise_db():
        raise DBError("Connection refused")

    @app.get("/auth-error")
    def raise_auth():
        raise AuthError("Token expired")

    @app.get("/esl-error")
    def raise_esl():
        raise ESLError("Action vetoed")

    return TestClient(app)


class TestErrorHandlers:
    def test_integration_error_returns_502(self, app_with_handlers):
        resp = app_with_handlers.get("/integration-error")
        assert resp.status_code == 502
        assert resp.json()["error"] == "integration_error"
        assert "Composio is down" in resp.json()["detail"]

    def test_db_error_returns_503(self, app_with_handlers):
        resp = app_with_handlers.get("/db-error")
        assert resp.status_code == 503
        assert resp.json()["error"] == "db_error"

    def test_auth_error_returns_401(self, app_with_handlers):
        resp = app_with_handlers.get("/auth-error")
        assert resp.status_code == 401

    def test_esl_error_returns_403(self, app_with_handlers):
        resp = app_with_handlers.get("/esl-error")
        assert resp.status_code == 403
