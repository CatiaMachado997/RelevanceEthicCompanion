"""Tests for AutoResearch API routes."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


def _make_client():
    """Create a TestClient with Weaviate patched out."""
    with patch("utils.weaviate_client.get_weaviate_client", return_value=None):
        from main import app
        return TestClient(app, raise_server_exceptions=False)


def test_autolab_status_returns_all_tracks():
    """GET /api/autolab/status returns dict with all three tracks."""
    client = _make_client()
    with patch("routes.autolab.autolab_settings") as mock_settings, \
         patch("routes.autolab.ObsidianClient") as mock_obs_cls:
        mock_settings.fallback_dir = "/nonexistent/path"
        mock_settings.obsidian_api_key = ""
        mock_settings.obsidian_base_url = "https://127.0.0.1:27124"
        mock_settings.obsidian_vault_path = "EthicCompanion"
        mock_obs_cls.return_value.ping.return_value = False
        response = client.get("/api/autolab/status")
    assert response.status_code == 200
    data = response.json()
    assert "tracks" in data
    assert set(data["tracks"].keys()) == {"esl_tuning", "prompt_opt", "context_scoring"}


def test_autolab_run_starts_background_task():
    """POST /api/autolab/run returns 200 for valid track."""
    client = _make_client()
    response = client.post("/api/autolab/run", json={"track": "esl_tuning", "max_trials": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["track"] == "esl_tuning"


def test_autolab_run_rejects_unknown_track():
    """POST /api/autolab/run returns 400 for unknown track."""
    client = _make_client()
    response = client.post("/api/autolab/run", json={"track": "invalid_track", "max_trials": 1})
    assert response.status_code == 400


def test_insights_endpoint_returns_structure():
    """GET /api/insights returns expected keys."""
    client = _make_client()
    with patch("routes.autolab.autolab_settings") as mock_settings, \
         patch("routes.autolab.ObsidianClient") as mock_obs_cls:
        mock_settings.fallback_dir = "/nonexistent/path"
        mock_settings.obsidian_api_key = ""
        mock_settings.obsidian_base_url = "https://127.0.0.1:27124"
        mock_settings.obsidian_vault_path = "EthicCompanion"
        mock_obs_cls.return_value.ping.return_value = False
        response = client.get("/api/insights")
    assert response.status_code == 200
    data = response.json()
    assert "autolab" in data
    assert "best_scores" in data["autolab"]
    assert "total_trials" in data["autolab"]
