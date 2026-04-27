"""Tests for AutoResearch API routes.

Tests the router in isolation (no `main` import) to avoid requiring
uvicorn, weaviate, and other heavy dependencies.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Build a minimal test app containing only the autolab routes
from routes.autolab import router, insights_router

_test_app = FastAPI()
_test_app.include_router(router)
_test_app.include_router(insights_router)

client = TestClient(_test_app, raise_server_exceptions=False)


def test_autolab_status_returns_all_tracks():
    """GET /api/autolab/status returns dict with all three tracks."""
    with patch("routes.autolab._fallback_dir", return_value=Path("/nonexistent/path")), \
         patch("routes.autolab._obsidian_client") as mock_obs:
        mock_obs.return_value.ping.return_value = False
        response = client.get("/api/autolab/status")
    assert response.status_code == 200
    data = response.json()
    assert "tracks" in data
    assert set(data["tracks"].keys()) == {"esl_tuning", "prompt_opt", "context_scoring"}


def test_autolab_run_starts_background_task():
    """POST /api/autolab/run returns 200 for valid track."""
    response = client.post("/api/autolab/run", json={"track": "esl_tuning", "max_trials": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["track"] == "esl_tuning"


def test_autolab_run_rejects_unknown_track():
    """POST /api/autolab/run returns 400 for unknown track."""
    response = client.post("/api/autolab/run", json={"track": "invalid_track", "max_trials": 1})
    assert response.status_code == 400


def test_insights_endpoint_returns_structure():
    """GET /api/insights returns expected keys."""
    with patch("routes.autolab._fallback_dir", return_value=Path("/nonexistent/path")):
        response = client.get("/api/insights")
    assert response.status_code == 200
    data = response.json()
    assert "autolab" in data
    assert "best_scores" in data["autolab"]
    assert "total_trials" in data["autolab"]
    assert "recent_experiments" in data
    assert "daily_insight" in data
