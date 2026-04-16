"""Tests for the /health endpoint."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def test_health_returns_ok_structure(test_client):
    """Health endpoint returns the expected JSON structure."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "components" in data
    assert "database" in data["components"]
    assert "weaviate" in data["components"]
    assert data["components"]["database"]["status"] in ("ok", "error")
    assert data["components"]["weaviate"]["status"] in ("ok", "unavailable", "error")


def test_health_weaviate_unavailable_does_not_crash():
    """When Weaviate is down, /health still returns 200 with weaviate=unavailable."""
    with patch("utils.weaviate_client.get_weaviate_client", return_value=None), patch(
        "utils.health.check_db", return_value={"status": "ok"}
    ):
        from main import app

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["components"]["weaviate"]["status"] == "unavailable"
        assert data["status"] == "ok"


def test_health_db_error_returns_degraded():
    """When DB is down, /health returns status=degraded."""
    # Patch check_db where it's used (in the routes.health module) as well as
    # where it's defined, because routes.health imports it at module load time.
    with patch("utils.weaviate_client.get_weaviate_client", return_value=None), patch(
        "routes.health.check_db",
        return_value={"status": "error", "detail": "connection refused"},
    ):
        from main import app

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["database"]["status"] == "error"
