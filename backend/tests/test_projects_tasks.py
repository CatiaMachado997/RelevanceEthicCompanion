# backend/tests/test_projects_tasks.py
"""Tests for Projects and Tasks API routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# ── shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_auth(monkeypatch):
    """Bypass auth — always return test user."""
    monkeypatch.setattr("utils.supabase_auth.get_current_user_id", lambda: "user-1")
    monkeypatch.setattr(
        "utils.supabase_auth.get_current_read_user_id", lambda: "user-1"
    )


@pytest.fixture
def mock_esl_approved():
    """ESL always approves."""
    decision = MagicMock()
    decision.status = "APPROVED"
    with patch("routes.projects.EthicalSafeguardLayer") as mock_cls, patch(
        "routes.tasks.EthicalSafeguardLayer"
    ) as mock_cls2:
        for m in (mock_cls, mock_cls2):
            m.return_value.evaluate_action = AsyncMock(return_value=decision)
        yield


@pytest.fixture
def mock_esl_vetoed():
    """ESL always vetoes."""
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.projects.EthicalSafeguardLayer") as mock_cls, patch(
        "routes.tasks.EthicalSafeguardLayer"
    ) as mock_cls2:
        for m in (mock_cls, mock_cls2):
            m.return_value.evaluate_action = AsyncMock(return_value=decision)
        yield


# ── Project tests ────────────────────────────────────────────────────────────


def test_list_projects_returns_list():
    """GET /api/projects should return 200 and a list."""
    from main import app

    client = TestClient(app)
    with patch(
        "routes.projects.get_current_read_user_id", return_value="user-1"
    ), patch("routes.projects.get_user_projects", return_value=[]):
        response = client.get("/api/projects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_project_esl_veto():
    """POST /api/projects should return 403 when ESL vetoes."""
    from main import app

    client = TestClient(app)
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.projects.get_current_user_id", return_value="user-1"), patch(
        "routes.projects.EthicalSafeguardLayer"
    ) as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = client.post("/api/projects", json={"title": "Test"})
    assert response.status_code == 403


def test_update_project_esl_veto():
    """PATCH /api/projects/{id} should return 403 when ESL vetoes."""
    from main import app

    client = TestClient(app)
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.projects.get_current_user_id", return_value="user-1"), patch(
        "routes.projects.EthicalSafeguardLayer"
    ) as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = client.patch("/api/projects/some-id", json={"title": "Updated"})
    assert response.status_code == 403


def test_archive_project_esl_veto():
    """DELETE /api/projects/{id} should return 403 when ESL vetoes."""
    from main import app

    client = TestClient(app)
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.projects.get_current_user_id", return_value="user-1"), patch(
        "routes.projects.EthicalSafeguardLayer"
    ) as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = client.delete("/api/projects/some-id")
    assert response.status_code == 403


# ── Task tests ───────────────────────────────────────────────────────────────


def test_list_tasks_returns_list():
    """GET /api/tasks should return 200 and a list."""
    from main import app

    client = TestClient(app)
    with patch("routes.tasks.get_current_read_user_id", return_value="user-1"), patch(
        "routes.tasks.get_user_tasks", return_value=[]
    ):
        response = client.get("/api/tasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_task_esl_veto():
    """POST /api/tasks should return 403 when ESL vetoes."""
    from main import app

    client = TestClient(app)
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.tasks.get_current_user_id", return_value="user-1"), patch(
        "routes.tasks.EthicalSafeguardLayer"
    ) as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = client.post("/api/tasks", json={"title": "Test task"})
    assert response.status_code == 403


def test_update_task_esl_veto():
    """PATCH /api/tasks/{id} should return 403 when ESL vetoes."""
    from main import app

    client = TestClient(app)
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.tasks.get_current_user_id", return_value="user-1"), patch(
        "routes.tasks.EthicalSafeguardLayer"
    ) as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = client.patch("/api/tasks/some-id", json={"status": "done"})
    assert response.status_code == 403


def test_delete_task_esl_veto():
    """DELETE /api/tasks/{id} should return 403 when ESL vetoes."""
    from main import app

    client = TestClient(app)
    decision = MagicMock()
    decision.status = "VETOED"
    decision.reason = "test veto"
    with patch("routes.tasks.get_current_user_id", return_value="user-1"), patch(
        "routes.tasks.EthicalSafeguardLayer"
    ) as mock_cls:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        response = client.delete("/api/tasks/some-id")
    assert response.status_code == 403


def test_extract_tasks_returns_suggestions():
    """POST /api/tasks/extract should return a list of suggestions (not stored)."""
    from main import app

    client = TestClient(app)
    decision = MagicMock()
    decision.status = "APPROVED"
    mock_ai_response = MagicMock()
    mock_ai_response.content = '{"tasks": [{"title": "Review doc", "description": "Check the spec", "priority": 3}]}'
    with patch("routes.tasks.get_current_user_id", return_value="user-1"), patch(
        "routes.tasks.EthicalSafeguardLayer"
    ) as mock_cls, patch("routes.tasks.ChatGroq") as mock_llm:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        mock_llm.return_value.invoke = MagicMock(return_value=mock_ai_response)
        response = client.post(
            "/api/tasks/extract", json={"text": "Review the spec document."}
        )
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)


def test_extract_tasks_bad_json_returns_empty():
    """POST /api/tasks/extract returns empty suggestions if LLM returns bad JSON."""
    from main import app

    client = TestClient(app)
    decision = MagicMock()
    decision.status = "APPROVED"
    mock_ai_response = MagicMock()
    mock_ai_response.content = "not valid json"
    with patch("routes.tasks.get_current_user_id", return_value="user-1"), patch(
        "routes.tasks.EthicalSafeguardLayer"
    ) as mock_cls, patch("routes.tasks.ChatGroq") as mock_llm:
        mock_cls.return_value.evaluate_action = AsyncMock(return_value=decision)
        mock_llm.return_value.invoke = MagicMock(return_value=mock_ai_response)
        response = client.post("/api/tasks/extract", json={"text": "bad text"})
    assert response.status_code == 200
    assert response.json()["suggestions"] == []
