"""
End-to-end smoke test for the trust pipeline.

Verifies the most-load-bearing seam in Ethic Companion:

    proposed action → ESL evaluation → audit log → transparency API
                                                  → feedback API

Each piece has its own unit tests. This test exists to catch *wiring*
regressions — a unit-test-clean codebase where the audit logger and the
transparency endpoint stop sharing the same logger instance, for example,
would still pass every other test but break this one.

Scope deliberately small:
  - Real ESL engine, real ESLAuditLogger (in-memory).
  - Mocked auth + context manager (we are not testing those here).
  - No LLM calls (pass `llm=None` so semantic checks are skipped).
  - No DB (in-memory audit logger; feedback processor is mocked).

Run with:

    pytest tests/test_e2e_smoke.py -v
"""

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from esl.audit import ESLAuditLogger
from esl.engine import EthicalSafeguardLayer
from esl.models import (
    ActionType,
    ESLDecisionStatus,
    ProposedAction,
    UrgencyLevel,
    UserContext,
    UserValue,
    ValueType,
)
from routes.feedback import (
    get_feedback_processor,
    router as feedback_router,
)
from routes.transparency import (
    get_audit_logger,
    router as transparency_router,
)
from utils.supabase_auth import (
    get_current_read_user_id,
    get_current_user_id,
)

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_context_manager(user_values: list[UserValue] | None = None):
    """Mock context manager returning a UserContext for ESL evaluation."""
    cm = MagicMock()
    cm.get_user_context = AsyncMock(
        return_value=UserContext(
            user_id=TEST_USER_ID,
            current_time=datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC),
            focus_mode=False,
            user_values=user_values or [],
        )
    )
    return cm


def _make_app(audit_logger: ESLAuditLogger, feedback_processor=None) -> FastAPI:
    """Build a minimal FastAPI app wired to the shared logger + auth overrides."""
    app = FastAPI()
    app.include_router(transparency_router)
    app.include_router(feedback_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_audit_logger] = lambda: audit_logger
    if feedback_processor is not None:
        app.dependency_overrides[get_feedback_processor] = lambda: feedback_processor
    return app


# ── The smoke ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_smoke_approved_decision_reaches_transparency_api():
    """
    Trust pipeline, happy path:
      ESL approves a benign action → audit log captures it → /transparency/logs
      surfaces it → /transparency/report counts it as approved.

    The shared `ESLAuditLogger` is the load-bearing seam; if the route's
    `Depends(get_audit_logger)` ever gets wired to a different instance,
    `total_count` would be 0 here even though the ESL ran fine.
    """
    audit_logger = ESLAuditLogger()
    esl = EthicalSafeguardLayer(
        context_manager=_make_context_manager(),
        audit_logger=audit_logger,
        llm=None,
    )

    action = ProposedAction(
        action_type=ActionType.CHAT_RESPONSE,
        content_type="chat",
        urgency=UrgencyLevel.MEDIUM,
        content="What should I focus on today?",
    )
    decision = await esl.evaluate_action(action, TEST_USER_ID)
    assert (
        decision.status == ESLDecisionStatus.APPROVED
    ), f"benign chat should pass ESL; got {decision.status}: {decision.reason}"

    client = TestClient(_make_app(audit_logger))

    logs_resp = client.get("/api/transparency/logs")
    assert logs_resp.status_code == 200
    body = logs_resp.json()
    assert body["total_count"] >= 1, body
    statuses = [log["decision_status"] for log in body["logs"]]
    assert "APPROVED" in statuses

    # `/stats` reads from the same logger via Depends(get_audit_logger);
    # it's the cleanest way to assert the dependency override actually
    # connects the two without dragging OrchestratorV2 (used by /report)
    # into the smoke test.
    stats_resp = client.get("/api/transparency/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_decisions"] >= 1, stats
    assert stats["approval_rate"] > 0, stats


@pytest.mark.asyncio
async def test_smoke_vetoed_decision_reaches_transparency_api():
    """
    Trust pipeline, veto path:
      User has a `no_politics` topic-filter value → ESL hard-vetoes a
      politics action → audit log captures the VETOED decision →
      /transparency/logs returns it with status='VETOED' and the
      violated value id surfaces in `violated_values`.

    Hard veto is the most safety-critical path; this catches regressions
    where TopicFilter or audit logging silently stop tagging the
    violated values list.
    """
    audit_logger = ESLAuditLogger()
    # `TopicFilter` extracts the blocked token via
    # `value.lower().replace("no_", "").replace("_", " ")`, so for
    # value="no_politics" the blocked token is "politics" (the bare word).
    politics_boundary = UserValue(
        id="value-no-politics",
        user_id=TEST_USER_ID,
        type=ValueType.TOPIC_FILTER,
        value="no_politics",
        priority=1,
        active=True,
    )
    esl = EthicalSafeguardLayer(
        context_manager=_make_context_manager([politics_boundary]),
        audit_logger=audit_logger,
        llm=None,
    )

    # TopicFilter does substring match on `value.value` (with `no_` stripped),
    # so the content must contain the literal blocked token "politics".
    action = ProposedAction(
        action_type=ActionType.CONTENT_GENERATION,
        content_type="commentary",
        urgency=UrgencyLevel.MEDIUM,
        content="Here is my take on US politics and the latest election.",
    )
    decision = await esl.evaluate_action(action, TEST_USER_ID)
    assert (
        decision.status == ESLDecisionStatus.VETOED
    ), f"politics action should be vetoed by topic filter; got {decision.status}"

    client = TestClient(_make_app(audit_logger))

    resp = client.get("/api/transparency/logs", params={"decision_status": "VETOED"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] >= 1, body
    veto_logs = [log for log in body["logs"] if log["decision_status"] == "VETOED"]
    assert veto_logs, "expected at least one VETOED log entry"
    # The violated value id should propagate end-to-end.
    assert any("value-no-politics" in log["violated_values"] for log in veto_logs)


def test_smoke_feedback_submission_returns_200():
    """
    Feedback API end-to-end (route → processor → 200 response).

    We mock `FeedbackProcessor` rather than the DB underneath because
    the smoke test's job is to verify the *route is reachable and shaped
    right*, not that the persistence layer works (test_feedback covers that).
    """
    processor = MagicMock()
    processor.submit_feedback = AsyncMock(return_value={"id": "feedback-1"})
    processor.adjust_signal_from_feedback = AsyncMock(return_value=None)
    processor.note_esl_sensitivity_boost = AsyncMock(return_value=None)

    client = TestClient(_make_app(ESLAuditLogger(), processor))

    resp = client.post(
        "/api/feedback/",
        json={
            "item_id": "chat-msg-1",
            "item_type": "chat_response",
            "feedback_type": "thumbs_down",
            "additional_notes": "missed the point",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    processor.submit_feedback.assert_awaited_once()
    processor.adjust_signal_from_feedback.assert_awaited_once()
