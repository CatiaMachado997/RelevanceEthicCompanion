# backend/tests/test_projects_tasks.py
"""Tests for Projects and Tasks API routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from utils.supabase_auth import get_current_user_id, get_current_read_user_id

# ── shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def authed_client():
    """TestClient with FastAPI auth dependencies overridden to a fixed user.

    `patch("routes.X.get_current_user_id", ...)` does NOT work for FastAPI
    route deps — FastAPI captures the callable at route-registration time.
    """
    from main import app

    app.dependency_overrides[get_current_user_id] = lambda: "user-1"
    app.dependency_overrides[get_current_read_user_id] = lambda: "user-1"
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_current_read_user_id, None)


# ── Project tests ────────────────────────────────────────────────────────────


def test_list_projects_returns_list(authed_client):
    """GET /api/projects should return 200 and a list."""
    with patch("routes.projects.get_user_projects", return_value=[]):
        response = authed_client.get("/api/projects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_project_esl_veto(authed_client):
    """POST /api/projects should return 403 when ESL vetoes."""
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.projects.EthicalSafeguardLayer") as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = authed_client.post("/api/projects", json={"title": "Test"})
    assert response.status_code == 403


def test_update_project_esl_veto(authed_client):
    """PATCH /api/projects/{id} should return 403 when ESL vetoes."""
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.projects.EthicalSafeguardLayer") as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = authed_client.patch(
            "/api/projects/some-id", json={"title": "Updated"}
        )
    assert response.status_code == 403


def test_archive_project_esl_veto(authed_client):
    """DELETE /api/projects/{id} should return 403 when ESL vetoes."""
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.projects.EthicalSafeguardLayer") as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = authed_client.delete("/api/projects/some-id")
    assert response.status_code == 403


# ── Task tests ───────────────────────────────────────────────────────────────


def test_list_tasks_returns_list(authed_client):
    """GET /api/tasks should return 200 and a list."""
    with patch("routes.tasks.get_user_tasks", return_value=[]):
        response = authed_client.get("/api/tasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_task_esl_veto(authed_client):
    """POST /api/tasks should return 403 when ESL vetoes."""
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.tasks.EthicalSafeguardLayer") as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = authed_client.post("/api/tasks", json={"title": "Test task"})
    assert response.status_code == 403


def test_update_task_esl_veto(authed_client):
    """PATCH /api/tasks/{id} should return 403 when ESL vetoes."""
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.tasks.EthicalSafeguardLayer") as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = authed_client.patch("/api/tasks/some-id", json={"status": "done"})
    assert response.status_code == 403


def test_delete_task_esl_veto(authed_client):
    """DELETE /api/tasks/{id} should return 403 when ESL vetoes."""
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.tasks.EthicalSafeguardLayer") as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = authed_client.delete("/api/tasks/some-id")
    assert response.status_code == 403


def test_extract_tasks_returns_suggestions(authed_client):
    """POST /api/tasks/extract should return a list of suggestions (not stored)."""
    decision = MagicMock()
    decision.status = "APPROVED"
    mock_ai_response = MagicMock()
    mock_ai_response.content = '{"tasks": [{"title": "Review doc", "description": "Check the spec", "priority": 3}]}'
    with patch("routes.tasks.EthicalSafeguardLayer") as mock_cls, patch(
        "routes.tasks.ChatGroq"
    ) as mock_llm:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        mock_llm.return_value.invoke = MagicMock(return_value=mock_ai_response)
        response = authed_client.post(
            "/api/tasks/extract", json={"text": "Review the spec document."}
        )
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)


def test_extract_tasks_bad_json_returns_empty(authed_client):
    """POST /api/tasks/extract returns empty suggestions if LLM returns bad JSON."""
    decision = MagicMock()
    decision.status = "APPROVED"
    mock_ai_response = MagicMock()
    mock_ai_response.content = "not valid json"
    with patch("routes.tasks.EthicalSafeguardLayer") as mock_cls, patch(
        "routes.tasks.ChatGroq"
    ) as mock_llm:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        mock_llm.return_value.invoke = MagicMock(return_value=mock_ai_response)
        response = authed_client.post("/api/tasks/extract", json={"text": "bad text"})
    assert response.status_code == 200
    assert response.json()["suggestions"] == []
