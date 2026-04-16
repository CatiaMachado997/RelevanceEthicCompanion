"""Tests for the transparency/audit log endpoint."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, UTC

from routes.transparency import (
    router as transparency_router,
    get_audit_logger,
    get_orchestrator,
)
from utils.supabase_auth import get_current_read_user_id
from esl.audit import ESLAuditLogger
from esl.models import (
    ESLAuditLog,
    ESLDecision,
    ESLDecisionStatus,
    ProposedAction,
    ActionType,
    UrgencyLevel,
)

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_sample_audit_log() -> ESLAuditLog:
    action = ProposedAction(
        action_type=ActionType.CHAT_RESPONSE,
        content_type="chat",
        urgency=UrgencyLevel.MEDIUM,
        content="Hello",
    )
    decision = ESLDecision(
        status=ESLDecisionStatus.APPROVED,
        reason="Action aligns with user values",
        confidence=0.95,
    )
    return ESLAuditLog(
        id="test-log-id-1",
        user_id=TEST_USER_ID,
        timestamp=datetime(2026, 3, 26, 12, 0, 0, tzinfo=UTC),
        proposed_action=action,
        decision=decision,
        context_snapshot={"focus_mode": False},
    )


def make_app():
    app = FastAPI()
    app.include_router(transparency_router)
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return app


# ── /api/transparency/logs ─────────────────────────────────────────────────────


def test_transparency_logs_returns_list():
    """GET /api/transparency/logs returns a list shape with 'logs' key."""
    mock_logger = MagicMock(spec=ESLAuditLogger)
    mock_logger.get_user_logs = AsyncMock(return_value=[])

    app = make_app()
    app.dependency_overrides[get_audit_logger] = lambda: mock_logger

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/transparency/logs")

    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
    assert isinstance(data["logs"], list)
    assert data["user_id"] == TEST_USER_ID
    assert data["total_count"] == 0


def test_transparency_logs_returns_flattened_entries():
    """GET /api/transparency/logs returns flat log entries with expected fields."""
    sample_log = make_sample_audit_log()
    mock_logger = MagicMock(spec=ESLAuditLogger)
    mock_logger.get_user_logs = AsyncMock(return_value=[sample_log])

    app = make_app()
    app.dependency_overrides[get_audit_logger] = lambda: mock_logger

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/transparency/logs")

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 1
    assert len(data["logs"]) == 1

    log = data["logs"][0]
    # Verify flat structure expected by the frontend
    assert "action_type" in log
    assert "decision_status" in log
    assert "reason" in log
    assert log["decision_status"] == "APPROVED"
    assert log["action_type"] == "chat_response"


def test_transparency_logs_filters_by_status():
    """GET /api/transparency/logs passes decision_status filter to audit logger."""
    mock_logger = MagicMock(spec=ESLAuditLogger)
    mock_logger.get_user_logs = AsyncMock(return_value=[])

    app = make_app()
    app.dependency_overrides[get_audit_logger] = lambda: mock_logger

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/transparency/logs?decision_status=VETOED")

    assert response.status_code == 200
    mock_logger.get_user_logs.assert_awaited_once()
    call_kwargs = mock_logger.get_user_logs.call_args
    assert call_kwargs.kwargs.get("status_filter") == "VETOED"


# ── /api/transparency/stats ───────────────────────────────────────────────────


def test_transparency_stats_returns_dict():
    """GET /api/transparency/stats returns a dict with statistics."""
    mock_logger = MagicMock(spec=ESLAuditLogger)
    mock_logger.get_statistics = AsyncMock(
        return_value={
            "total_decisions": 0,
            "approval_rate": 0.0,
            "veto_rate": 0.0,
            "modification_rate": 0.0,
            "most_common_violations": [],
            "most_active_rules": [],
        }
    )

    app = make_app()
    app.dependency_overrides[get_audit_logger] = lambda: mock_logger

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/transparency/stats")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


# ── /api/transparency/insights ────────────────────────────────────────────────


def test_transparency_insights_returns_insights_list():
    """GET /api/transparency/insights returns an insights list."""
    mock_logger = MagicMock(spec=ESLAuditLogger)
    mock_logger.get_user_logs = AsyncMock(return_value=[])

    app = make_app()
    app.dependency_overrides[get_audit_logger] = lambda: mock_logger

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/transparency/insights")

    assert response.status_code == 200
    data = response.json()
    assert "insights" in data
    assert isinstance(data["insights"], list)


def test_transparency_insights_with_logs():
    """GET /api/transparency/insights returns non-empty insights when logs exist."""
    sample_log = make_sample_audit_log()
    mock_logger = MagicMock(spec=ESLAuditLogger)
    mock_logger.get_user_logs = AsyncMock(return_value=[sample_log])

    app = make_app()
    app.dependency_overrides[get_audit_logger] = lambda: mock_logger

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/transparency/insights")

    assert response.status_code == 200
    data = response.json()
    assert len(data["insights"]) > 0


# ── audit logger writes on all decision paths ─────────────────────────────────


@pytest.mark.asyncio
async def test_audit_logger_logs_approved_decision():
    """ESLAuditLogger.log_decision stores APPROVED decisions in memory."""
    logger = ESLAuditLogger()
    action = ProposedAction(
        action_type=ActionType.CHAT_RESPONSE,
        content_type="chat",
        urgency=UrgencyLevel.LOW,
    )
    decision = ESLDecision(
        status=ESLDecisionStatus.APPROVED,
        reason="Approved",
        confidence=0.9,
    )
    await logger.log_decision(
        user_id=TEST_USER_ID,
        proposed_action=action,
        decision=decision,
        context_snapshot={},
    )
    logs = await logger.get_user_logs(TEST_USER_ID)
    assert len(logs) == 1
    assert logs[0].decision.status == ESLDecisionStatus.APPROVED


@pytest.mark.asyncio
async def test_audit_logger_logs_vetoed_decision():
    """ESLAuditLogger.log_decision stores VETOED decisions in memory."""
    logger = ESLAuditLogger()
    action = ProposedAction(
        action_type=ActionType.PUSH_NOTIFICATION,
        content_type="work_summary",
        urgency=UrgencyLevel.HIGH,
    )
    decision = ESLDecision(
        status=ESLDecisionStatus.VETOED,
        reason="Violates boundary",
        confidence=0.95,
    )
    await logger.log_decision(
        user_id=TEST_USER_ID,
        proposed_action=action,
        decision=decision,
        context_snapshot={},
    )
    logs = await logger.get_user_logs(TEST_USER_ID)
    assert len(logs) == 1
    assert logs[0].decision.status == ESLDecisionStatus.VETOED


@pytest.mark.asyncio
async def test_audit_logger_logs_modified_decision():
    """ESLAuditLogger.log_decision stores MODIFIED decisions in memory."""
    logger = ESLAuditLogger()
    action = ProposedAction(
        action_type=ActionType.REMINDER,
        content_type="reminder",
        urgency=UrgencyLevel.MEDIUM,
    )
    decision = ESLDecision(
        status=ESLDecisionStatus.MODIFIED,
        reason="Delayed to appropriate time",
        confidence=0.90,
    )
    await logger.log_decision(
        user_id=TEST_USER_ID,
        proposed_action=action,
        decision=decision,
        context_snapshot={},
    )
    logs = await logger.get_user_logs(TEST_USER_ID)
    assert len(logs) == 1
    assert logs[0].decision.status == ESLDecisionStatus.MODIFIED
