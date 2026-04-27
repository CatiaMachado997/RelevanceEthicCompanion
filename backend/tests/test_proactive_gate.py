"""Tests for backend.services.proactive_gate.gate_proactive_notification.

Sprint C Task 3 — verifies the ESL gate for scheduler-emitted notifications:
APPROVED → send original; MODIFIED → send modified text; VETOED → drop;
exception → fail-closed (drop) and log.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from esl.models import (
    ProposedAction,
    ESLDecision,
    ESLDecisionStatus,
    ActionType,
    UrgencyLevel,
)
from services import proactive_gate


def _make_esl(decision_or_exc):
    """Build a mock ESL whose evaluate_action returns/raises the given value."""
    esl = MagicMock()
    if isinstance(decision_or_exc, BaseException):
        esl.evaluate_action = AsyncMock(side_effect=decision_or_exc)
    else:
        esl.evaluate_action = AsyncMock(return_value=decision_or_exc)
    return esl


@pytest.mark.asyncio
async def test_approved_returns_send_with_content(monkeypatch):
    decision = ESLDecision(
        status=ESLDecisionStatus.APPROVED,
        reason="Action aligns with user values",
        confidence=0.95,
    )
    monkeypatch.setattr(proactive_gate, "get_esl", lambda: _make_esl(decision))

    should_send, final = await proactive_gate.gate_proactive_notification(
        user_id="user-1",
        notification_type="daily_focus_plan",
        content="Here's your morning focus plan.",
        urgency="low",
    )

    assert should_send is True
    assert final == "Here's your morning focus plan."


@pytest.mark.asyncio
async def test_vetoed_returns_no_send(monkeypatch):
    decision = ESLDecision(
        status=ESLDecisionStatus.VETOED,
        reason="Violates user boundary: no_work_after_19h",
        violated_values=["value-1"],
        confidence=0.95,
    )
    monkeypatch.setattr(proactive_gate, "get_esl", lambda: _make_esl(decision))

    should_send, final = await proactive_gate.gate_proactive_notification(
        user_id="user-1",
        notification_type="pre_meeting_brief",
        content="You have a meeting in 15 minutes.",
        urgency="medium",
    )

    assert should_send is False
    assert final == "You have a meeting in 15 minutes."


@pytest.mark.asyncio
async def test_modified_returns_send_with_modified_text(monkeypatch):
    modified_action = ProposedAction(
        action_type=ActionType.PUSH_NOTIFICATION,
        content_type="deadline_warning",
        content="Softened: deadline approaching tomorrow.",
        urgency=UrgencyLevel.LOW,
    )
    decision = ESLDecision(
        status=ESLDecisionStatus.MODIFIED,
        reason="Reframed to reduce urgency manipulation",
        modified_action=modified_action,
        confidence=0.90,
    )
    monkeypatch.setattr(proactive_gate, "get_esl", lambda: _make_esl(decision))

    should_send, final = await proactive_gate.gate_proactive_notification(
        user_id="user-1",
        notification_type="deadline_warning",
        content="URGENT!!! Deadline tomorrow, don't miss it!",
        urgency="high",
    )

    assert should_send is True
    assert final == "Softened: deadline approaching tomorrow."


@pytest.mark.asyncio
async def test_esl_exception_fails_closed(monkeypatch, caplog):
    monkeypatch.setattr(
        proactive_gate,
        "get_esl",
        lambda: _make_esl(RuntimeError("ESL backend unavailable")),
    )

    with caplog.at_level(logging.WARNING, logger=proactive_gate.logger.name):
        should_send, final = await proactive_gate.gate_proactive_notification(
            user_id="user-1",
            notification_type="weekly_digest",
            content="Weekly digest body.",
            urgency="low",
        )

    assert should_send is False
    assert final == "Weekly digest body."
    # Exception was logged
    assert any(
        "ESL evaluation failed" in record.getMessage()
        and "ESL backend unavailable" in record.getMessage()
        for record in caplog.records
    )
