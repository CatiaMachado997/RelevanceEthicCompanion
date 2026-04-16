"""
ESL (Ethical Safeguard Layer) Test Suite

Comprehensive tests for the core ESL components:
- TimeBasedRules
- ManipulationDetector
- EngagementDetector
- TopicFilter
- EthicalSafeguardLayer (integration)
- ESLAuditLogger
"""

import pytest
from contextlib import contextmanager
from datetime import datetime, UTC
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from esl.models import (
    ProposedAction,
    ESLDecision,
    ESLDecisionStatus,
    UserValue,
    UserContext,
    ValueType,
    ActionType,
    UrgencyLevel,
)
from esl.rules import (
    TimeBasedRules,
    ManipulationDetector,
    EngagementDetector,
    TopicFilter,
)
from esl.engine import EthicalSafeguardLayer
from esl.audit import ESLAuditLogger

# ==================== Fixtures ====================


@pytest.fixture
def time_rules():
    return TimeBasedRules()


@pytest.fixture
def manipulation_detector():
    return ManipulationDetector()


@pytest.fixture
def engagement_detector():
    return EngagementDetector()


@pytest.fixture
def topic_filter():
    return TopicFilter()


@pytest.fixture
def mock_context_manager():
    """Create a mock context manager for ESL tests"""
    cm = MagicMock()
    cm.get_user_context = AsyncMock(
        return_value=UserContext(
            user_id="test-user-123",
            current_time=datetime.now(UTC),
            focus_mode=False,
            active_goals=["goal-1"],
            user_values=[],
        )
    )
    return cm


@pytest.fixture
def esl(mock_context_manager):
    return EthicalSafeguardLayer(mock_context_manager)


@pytest.fixture
def audit_logger():
    return ESLAuditLogger()


def create_action(
    action_type: ActionType = ActionType.CHAT_RESPONSE,
    content: str = "Test content",
    content_type: str = "text",
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
    metadata: Optional[dict] = None,
) -> ProposedAction:
    """Helper to create ProposedAction instances"""
    return ProposedAction(
        action_type=action_type,
        content=content,
        content_type=content_type,
        urgency=urgency,
        metadata=metadata or {},
    )


def create_user_value(
    value_type: ValueType,
    value: str,
    priority: int = 1,
    active: bool = True,
    user_id: str = "test-user",
) -> UserValue:
    """Helper to create UserValue instances"""
    return UserValue(
        id=f"value-{value}",
        user_id=user_id,
        type=value_type,
        value=value,
        priority=priority,
        active=active,
    )


# ==================== TimeBasedRules Tests ====================


class TestTimeBasedRules:
    """Tests for time-based boundary enforcement"""

    def test_allows_work_during_work_hours(self, time_rules):
        """Work actions should be allowed during work hours"""
        action = create_action(content_type="work_summary")
        values = [create_user_value(ValueType.BOUNDARY, "no_work_after_19h")]
        work_time = datetime(2025, 1, 15, 14, 0)  # 2 PM

        result = time_rules.check_boundaries(action, values, work_time)

        assert result.passed is True
        assert len(result.violated_values) == 0

    def test_blocks_work_after_hours(self, time_rules):
        """Work actions should be blocked after user's cutoff hour"""
        action = create_action(content_type="work_summary")
        values = [create_user_value(ValueType.BOUNDARY, "no_work_after_19h")]
        evening_time = datetime(2025, 1, 15, 20, 0)  # 8 PM

        result = time_rules.check_boundaries(action, values, evening_time)

        assert result.passed is False
        assert "no_work_after_19h" in result.reason
        assert len(result.violated_values) > 0

    def test_blocks_during_quiet_hours(self, time_rules):
        """Actions should be blocked during quiet hours"""
        action = create_action(content_type="notification")
        values = [create_user_value(ValueType.BOUNDARY, "quiet_hours_enabled")]
        late_night = datetime(2025, 1, 15, 23, 0)  # 11 PM

        result = time_rules.check_boundaries(action, values, late_night)

        assert result.passed is False
        assert "quiet hours" in result.reason.lower()

    def test_allows_during_day_with_quiet_hours(self, time_rules):
        """Actions should be allowed during daytime even with quiet hours enabled"""
        action = create_action(content_type="notification")
        values = [create_user_value(ValueType.BOUNDARY, "quiet_hours_enabled")]
        daytime = datetime(2025, 1, 15, 12, 0)  # Noon

        result = time_rules.check_boundaries(action, values, daytime)

        assert result.passed is True

    def test_inactive_boundary_ignored(self, time_rules):
        """Inactive boundaries should not be enforced"""
        action = create_action(content_type="work_summary")
        values = [
            create_user_value(ValueType.BOUNDARY, "no_work_after_19h", active=False)
        ]
        evening_time = datetime(2025, 1, 15, 21, 0)  # 9 PM

        result = time_rules.check_boundaries(action, values, evening_time)

        assert result.passed is True

    def test_non_boundary_values_ignored(self, time_rules):
        """Non-boundary value types should be ignored by time rules"""
        action = create_action(content_type="work_summary")
        values = [create_user_value(ValueType.PREFERENCE, "no_work_after_19h")]
        evening_time = datetime(2025, 1, 15, 21, 0)  # 9 PM

        result = time_rules.check_boundaries(action, values, evening_time)

        assert result.passed is True


# ==================== ManipulationDetector Tests ====================


class TestManipulationDetector:
    """Tests for psychological manipulation detection"""

    def test_allows_normal_content(self, manipulation_detector):
        """Normal content should pass"""
        result = manipulation_detector.check_content(
            "Here's your meeting summary for today."
        )

        assert result.passed is True
        assert "No manipulation patterns" in result.reason

    def test_single_fomo_pattern_allowed(self, manipulation_detector):
        """Single FOMO pattern alone should pass (requires ≥2 to flag)"""
        result = manipulation_detector.check_content(
            "Don't miss out on this opportunity!"
        )

        assert result.passed is True

    def test_single_fomo_last_chance_allowed(self, manipulation_detector):
        """Single 'last chance' pattern alone should pass"""
        result = manipulation_detector.check_content(
            "This is your last chance to respond!"
        )

        assert result.passed is True

    def test_detects_fomo_combined_with_urgency(self, manipulation_detector):
        """≥2 manipulation patterns together should be flagged"""
        result = manipulation_detector.check_content(
            "Limited time offer - act now! Don't miss out!"
        )

        assert result.passed is False
        assert "manipulation" in result.reason.lower()

    def test_detects_fomo_limited_time_act_now(self, manipulation_detector):
        """'limited time' + 'act now' triggers two patterns — should be flagged"""
        result = manipulation_detector.check_content("Limited time offer - act now!")

        assert result.passed is False

    def test_single_urgency_pattern_allowed(self, manipulation_detector):
        """Single artificial urgency pattern alone should pass"""
        result = manipulation_detector.check_content(
            "You must act immediately to avoid problems!"
        )

        assert result.passed is True

    def test_allows_genuine_urgent_meeting(self, manipulation_detector):
        """Should allow genuine urgent meeting notifications"""
        result = manipulation_detector.check_content(
            "Urgent meeting scheduled for 3 PM"
        )

        # The regex explicitly excludes "urgent meeting"
        assert result.passed is True

    def test_single_guilt_pattern_allowed(self, manipulation_detector):
        """Single guilt-tripping pattern alone should pass"""
        result = manipulation_detector.check_content(
            "You should have responded earlier."
        )

        assert result.passed is True

    def test_guilt_combined_with_fomo_flagged(self, manipulation_detector):
        """Guilt + FOMO together should be flagged"""
        result = manipulation_detector.check_content(
            "You forgot to respond! Last chance to act now."
        )

        assert result.passed is False
        assert "manipulation" in result.reason.lower()

    def test_handles_empty_content(self, manipulation_detector):
        """Should handle empty content gracefully"""
        result = manipulation_detector.check_content("")

        assert result.passed is True
        assert "No content" in result.reason

    def test_handles_none_content(self, manipulation_detector):
        """Should handle None content gracefully"""
        result = manipulation_detector.check_content(None)

        assert result.passed is True


# ==================== EngagementDetector Tests ====================


class TestEngagementDetector:
    """Tests for engagement vs assistance intent detection"""

    def test_allows_assistance_intent(self, engagement_detector):
        """Actions with assistance intent should pass"""
        action = create_action(metadata={"goal_relevance": 0.9, "user_request": True})

        result = engagement_detector.check_intent(action)

        assert result.passed is True
        assert "assistance" in result.reason.lower()

    def test_allows_single_engagement_metric(self, engagement_detector):
        """Single engagement metric alone should pass (score ≤ 0.7 threshold)"""
        action = create_action(metadata={"click_rate": 0.15})

        result = engagement_detector.check_intent(action)

        assert result.passed is True

    def test_allows_two_engagement_metrics(self, engagement_detector):
        """Two engagement metrics alone should pass (score ≤ 0.7)"""
        action = create_action(metadata={"time_in_app": 300, "click_rate": 0.15})

        result = engagement_detector.check_intent(action)

        assert result.passed is True

    def test_blocks_heavy_engagement_optimization(self, engagement_detector):
        """≥4 engagement metrics without assistance intent should be blocked (score > 0.7)"""
        action = create_action(
            metadata={
                "click_rate": 0.15,
                "time_in_app": 300,
                "daily_active": True,
                "session_length": 600,
            }
        )

        result = engagement_detector.check_intent(action)

        assert result.passed is False
        assert "engagement" in result.reason.lower()

    def test_blocks_critical_without_assistance_intent(self, engagement_detector):
        """Critical urgency without assistance intent should be suspicious"""
        action = create_action(urgency=UrgencyLevel.CRITICAL, metadata={})

        result = engagement_detector.check_intent(action)

        assert result.passed is False
        assert "manipulation" in result.reason.lower()

    def test_allows_critical_with_user_request(self, engagement_detector):
        """Critical urgency with user request should pass"""
        action = create_action(
            urgency=UrgencyLevel.CRITICAL, metadata={"user_request": True}
        )

        result = engagement_detector.check_intent(action)

        assert result.passed is True

    def test_allows_normal_action_without_metadata(self, engagement_detector):
        """Normal actions without suspicious metadata should pass"""
        action = create_action(urgency=UrgencyLevel.LOW, metadata={})

        result = engagement_detector.check_intent(action)

        assert result.passed is True


# ==================== TopicFilter Tests ====================


class TestTopicFilter:
    """Tests for topic-based content filtering"""

    def test_allows_unfiltered_topic(self, topic_filter):
        """Content without matching filters should pass"""
        action = create_action(content="Meeting notes for project alpha")
        values = [create_user_value(ValueType.TOPIC_FILTER, "no_politics")]

        result = topic_filter.check_topic(action, values)

        assert result.passed is True

    def test_blocks_filtered_topic_in_content(self, topic_filter):
        """Content matching topic filter should be blocked"""
        action = create_action(content="Latest politics news summary")
        values = [create_user_value(ValueType.TOPIC_FILTER, "no_politics")]

        result = topic_filter.check_topic(action, values)

        assert result.passed is False
        assert "topic filter" in result.reason.lower()

    def test_blocks_filtered_topic_in_content_type(self, topic_filter):
        """Content type matching topic filter should be blocked"""
        action = create_action(content="Update", content_type="politics_summary")
        values = [create_user_value(ValueType.TOPIC_FILTER, "no_politics")]

        result = topic_filter.check_topic(action, values)

        assert result.passed is False

    def test_inactive_filter_ignored(self, topic_filter):
        """Inactive topic filters should be ignored"""
        action = create_action(content="Politics discussion")
        values = [
            create_user_value(ValueType.TOPIC_FILTER, "no_politics", active=False)
        ]

        result = topic_filter.check_topic(action, values)

        assert result.passed is True

    def test_non_filter_values_ignored(self, topic_filter):
        """Non-filter value types should be ignored"""
        action = create_action(content="Politics discussion")
        values = [create_user_value(ValueType.BOUNDARY, "no_politics")]

        result = topic_filter.check_topic(action, values)

        assert result.passed is True

    def test_handles_empty_content(self, topic_filter):
        """Should handle empty content gracefully"""
        action = create_action(content="")
        values = [create_user_value(ValueType.TOPIC_FILTER, "no_politics")]

        result = topic_filter.check_topic(action, values)

        assert result.passed is True


# ==================== ESL Engine Integration Tests ====================


class TestEthicalSafeguardLayer:
    """Integration tests for the full ESL engine"""

    @pytest.mark.asyncio
    async def test_approves_safe_action(self, mock_context_manager):
        """Safe actions should be approved"""
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(content="Your meeting is in 10 minutes")

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.APPROVED
        assert decision.confidence > 0

    @pytest.mark.asyncio
    async def test_vetoes_manipulation(self, mock_context_manager):
        """Non-chat actions with ≥2 manipulation patterns should be vetoed"""
        esl = EthicalSafeguardLayer(mock_context_manager)
        # Use PUSH_NOTIFICATION (non-advisory) with multiple manipulation patterns
        action = create_action(
            action_type=ActionType.PUSH_NOTIFICATION,
            content="Don't miss out! Limited time offer — act now!",
        )

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.VETOED
        assert "manipulation" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_chat_manipulation_is_advisory(self, mock_context_manager):
        """Chat responses with manipulation patterns return APPROVED in advisory mode"""
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(
            action_type=ActionType.CHAT_RESPONSE,
            content="Don't miss out! Limited time offer — act now!",
        )

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.APPROVED
        assert "Advisory" in decision.reason

    @pytest.mark.asyncio
    async def test_vetoes_focus_mode_violation(self, mock_context_manager):
        """Non-critical actions during focus mode should be vetoed"""
        mock_context_manager.get_user_context = AsyncMock(
            return_value=UserContext(
                user_id="test-user",
                current_time=datetime.now(UTC),
                focus_mode=True,  # Focus mode enabled
                active_goals=[],
                user_values=[],
            )
        )
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(urgency=UrgencyLevel.LOW)

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.VETOED
        assert "focus mode" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_allows_critical_during_focus_mode(self, mock_context_manager):
        """Critical actions should be allowed even during focus mode"""
        mock_context_manager.get_user_context = AsyncMock(
            return_value=UserContext(
                user_id="test-user",
                current_time=datetime.now(UTC),
                focus_mode=True,
                active_goals=[],
                user_values=[],
            )
        )
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(
            urgency=UrgencyLevel.CRITICAL,
            metadata={"user_request": True},  # Has assistance intent
        )

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.APPROVED

    @pytest.mark.asyncio
    async def test_vetoes_time_boundary_violation(self, mock_context_manager):
        """Non-chat actions violating time boundaries should be vetoed"""
        mock_context_manager.get_user_context = AsyncMock(
            return_value=UserContext(
                user_id="test-user",
                current_time=datetime(2025, 1, 15, 21, 0),  # 9 PM
                focus_mode=False,
                active_goals=[],
                user_values=[
                    create_user_value(ValueType.BOUNDARY, "no_work_after_19h")
                ],
            )
        )
        esl = EthicalSafeguardLayer(mock_context_manager)
        # Use PUSH_NOTIFICATION (non-advisory) for time boundary test
        action = create_action(
            action_type=ActionType.PUSH_NOTIFICATION, content_type="work_summary"
        )

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.VETOED
        assert len(decision.violated_values) > 0

    @pytest.mark.asyncio
    async def test_chat_time_violation_is_advisory(self, mock_context_manager):
        """Chat responses with time boundary violations return APPROVED in advisory mode"""
        mock_context_manager.get_user_context = AsyncMock(
            return_value=UserContext(
                user_id="test-user",
                current_time=datetime(2025, 1, 15, 21, 0),  # 9 PM
                focus_mode=False,
                active_goals=[],
                user_values=[
                    create_user_value(ValueType.BOUNDARY, "no_work_after_19h")
                ],
            )
        )
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(
            action_type=ActionType.CHAT_RESPONSE, content_type="work_summary"
        )

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.APPROVED
        assert "Advisory" in decision.reason

    @pytest.mark.asyncio
    async def test_logs_all_decisions(self, mock_context_manager):
        """All decisions should be logged to audit"""
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action()

        # Make a decision
        await esl.evaluate_action(action, "test-user")

        # Check audit log
        logs = await esl.audit_logger.get_user_logs("test-user", days=1)
        assert len(logs) == 1
        assert logs[0].user_id == "test-user"


# ==================== ESL Audit Logger Tests ====================


class TestESLAuditLogger:
    """Tests for ESL audit logging"""

    @pytest.mark.asyncio
    async def test_logs_decision(self, audit_logger):
        """Should log decisions to memory"""
        action = create_action()
        decision = ESLDecision(
            status=ESLDecisionStatus.APPROVED,
            reason="Test approval",
            confidence=0.95,
        )

        await audit_logger.log_decision(
            user_id="test-user",
            proposed_action=action,
            decision=decision,
            context_snapshot={"test": True},
        )

        logs = await audit_logger.get_user_logs("test-user", days=1)
        assert len(logs) == 1
        assert logs[0].decision.status == ESLDecisionStatus.APPROVED

    @pytest.mark.asyncio
    async def test_filters_by_status(self, audit_logger):
        """Should filter logs by decision status"""
        action = create_action()

        # Log approved and vetoed decisions
        await audit_logger.log_decision(
            "test-user",
            action,
            ESLDecision(status=ESLDecisionStatus.APPROVED, reason="ok", confidence=0.9),
            {},
        )
        await audit_logger.log_decision(
            "test-user",
            action,
            ESLDecision(
                status=ESLDecisionStatus.VETOED, reason="blocked", confidence=0.9
            ),
            {},
        )

        vetoed_logs = await audit_logger.get_user_logs(
            "test-user", days=1, status_filter="VETOED"
        )
        assert len(vetoed_logs) == 1
        assert vetoed_logs[0].decision.status == ESLDecisionStatus.VETOED

    @pytest.mark.asyncio
    async def test_statistics_calculation(self, audit_logger):
        """Should calculate correct statistics"""
        action = create_action()

        # Log 3 approved, 1 vetoed
        for _ in range(3):
            await audit_logger.log_decision(
                "test-user",
                action,
                ESLDecision(
                    status=ESLDecisionStatus.APPROVED, reason="ok", confidence=0.9
                ),
                {},
            )
        await audit_logger.log_decision(
            "test-user",
            action,
            ESLDecision(
                status=ESLDecisionStatus.VETOED, reason="blocked", confidence=0.9
            ),
            {},
        )

        stats = await audit_logger.get_statistics("test-user", days=1)

        assert stats["total_decisions"] == 4
        assert stats["approval_rate"] == 0.75
        assert stats["veto_rate"] == 0.25

    @pytest.mark.asyncio
    async def test_isolates_users(self, audit_logger):
        """Should isolate logs between users"""
        action = create_action()

        await audit_logger.log_decision(
            "user-1",
            action,
            ESLDecision(status=ESLDecisionStatus.APPROVED, reason="ok", confidence=0.9),
            {},
        )
        await audit_logger.log_decision(
            "user-2",
            action,
            ESLDecision(
                status=ESLDecisionStatus.VETOED, reason="blocked", confidence=0.9
            ),
            {},
        )

        user1_logs = await audit_logger.get_user_logs("user-1", days=1)
        user2_logs = await audit_logger.get_user_logs("user-2", days=1)

        assert len(user1_logs) == 1
        assert len(user2_logs) == 1
        assert user1_logs[0].decision.status == ESLDecisionStatus.APPROVED
        assert user2_logs[0].decision.status == ESLDecisionStatus.VETOED


# ==================== ESL Audit Logger DB Persistence Tests ====================


def _make_mock_db_factory(rows=None, raise_on_enter=False):
    """Build a factory that mimics `with get_db_connection() as conn: with conn.cursor() as cur: ...`.

    If `raise_on_enter` is True, entering the outer context raises RuntimeError
    to simulate DB unavailability. Returned factory has `.executed` attached,
    a list capturing (query, params) pairs for inspection.
    """
    from contextlib import contextmanager

    executed = []

    @contextmanager
    def factory():
        if raise_on_enter:
            raise RuntimeError("DB unavailable")
        conn = MagicMock()
        cursor = MagicMock()
        cursor.execute.side_effect = lambda q, p=(): executed.append((q, p))
        cursor.fetchall.return_value = rows or []
        cursor_cm = MagicMock()
        cursor_cm.__enter__ = MagicMock(return_value=cursor)
        cursor_cm.__exit__ = MagicMock(return_value=None)
        conn.cursor.return_value = cursor_cm
        yield conn

    factory.executed = executed
    return factory


class TestESLAuditLoggerDatabase:
    """Tests for ESL audit logger when backed by a PostgreSQL-style connection.

    Covers the database-persistence code paths in esl/audit.py that are not
    exercised by the in-memory tests above (~60 lines of coverage).
    """

    @pytest.mark.asyncio
    async def test_db_log_decision_executes_insert(self):
        """log_decision with DB factory should issue INSERT with correct params."""
        factory = _make_mock_db_factory()
        logger_inst = ESLAuditLogger(db_connection_factory=factory)
        action = create_action()
        decision = ESLDecision(
            status=ESLDecisionStatus.APPROVED,
            reason="ok",
            confidence=0.9,
            applied_rules=["time_based_rules"],
            violated_values=[],
        )

        await logger_inst.log_decision(
            user_id="db-user-1",
            proposed_action=action,
            decision=decision,
            context_snapshot={"focus_mode": False},
        )

        assert len(factory.executed) == 1
        query, params = factory.executed[0]
        assert "INSERT INTO esl_audit_log" in query
        # positional params: user_id, timestamp, proposed_action, status, reason, ...
        assert params[0] == "db-user-1"
        assert params[3] == "APPROVED"
        assert params[4] == "ok"

    @pytest.mark.asyncio
    async def test_db_log_decision_falls_back_on_exception(self):
        """If DB factory raises, log should still be captured in memory."""
        failing_factory = _make_mock_db_factory(raise_on_enter=True)
        logger_inst = ESLAuditLogger(db_connection_factory=failing_factory)
        action = create_action()
        decision = ESLDecision(
            status=ESLDecisionStatus.VETOED, reason="blocked", confidence=0.8
        )

        await logger_inst.log_decision(
            user_id="db-user-2",
            proposed_action=action,
            decision=decision,
            context_snapshot={},
        )

        # Fallback path pushed into _in_memory_logs directly
        assert len(logger_inst._in_memory_logs) == 1
        assert logger_inst._in_memory_logs[0].user_id == "db-user-2"

    @pytest.mark.asyncio
    async def test_db_get_user_logs_returns_rows(self):
        """get_user_logs should convert DB rows into ESLAuditLog objects."""
        action_dict = {
            "action_type": "chat_response",
            "content": "hello",
            "content_type": "text",
            "urgency": "medium",
            "metadata": {},
        }
        rows = [
            {
                "id": "row-1",
                "user_id": "db-user-3",
                "timestamp": datetime.now(UTC),
                "proposed_action": action_dict,
                "decision_status": "APPROVED",
                "decision_reason": "safe",
                "violated_values": [],
                "applied_rules": ["time_based_rules"],
                "confidence": 0.95,
                "context_snapshot": {"focus_mode": False},
            }
        ]
        factory = _make_mock_db_factory(rows=rows)
        logger_inst = ESLAuditLogger(db_connection_factory=factory)

        logs = await logger_inst.get_user_logs("db-user-3", days=7)

        assert len(logs) == 1
        assert logs[0].user_id == "db-user-3"
        assert logs[0].decision.status == ESLDecisionStatus.APPROVED
        assert logs[0].decision.applied_rules == ["time_based_rules"]
        # Verify SELECT executed without AND decision_status (no filter)
        assert len(factory.executed) == 1
        query, _params = factory.executed[0]
        assert "SELECT" in query
        assert "decision_status = %s" not in query

    @pytest.mark.asyncio
    async def test_db_get_user_logs_with_status_filter(self):
        """status_filter should append an AND decision_status = %s clause."""
        factory = _make_mock_db_factory(rows=[])
        logger_inst = ESLAuditLogger(db_connection_factory=factory)

        await logger_inst.get_user_logs("db-user-4", days=30, status_filter="VETOED")

        assert len(factory.executed) == 1
        query, params = factory.executed[0]
        assert "decision_status = %s" in query
        assert "VETOED" in params

    @pytest.mark.asyncio
    async def test_db_get_user_logs_falls_back_on_exception(self):
        """If DB query raises, should fall back to in-memory logs."""
        failing_factory = _make_mock_db_factory(raise_on_enter=True)
        logger_inst = ESLAuditLogger(db_connection_factory=failing_factory)

        # Seed an in-memory log to prove fallback reads from there
        action = create_action()
        decision = ESLDecision(
            status=ESLDecisionStatus.APPROVED, reason="ok", confidence=0.9
        )
        # Manually insert (bypassing log_decision, which would also fail)
        from esl.models import ESLAuditLog

        logger_inst._in_memory_logs.append(
            ESLAuditLog(
                user_id="db-user-5",
                proposed_action=action,
                decision=decision,
                context_snapshot={},
                timestamp=datetime.now(UTC),
            )
        )

        logs = await logger_inst.get_user_logs("db-user-5", days=7)
        assert len(logs) == 1
        assert logs[0].user_id == "db-user-5"


# ==================== ESL Engine — content-safety and transparency ====================


def _make_sensitivity_db_factory(row=None, raise_on_enter=False):
    """Context-manager factory for engine.py sensitivity DB queries.

    Mirrors `with get_db_connection() as conn: with conn.cursor() as cur: ...`
    and records executed (query, params) pairs on the factory for inspection.
    """
    executed = []

    @contextmanager
    def factory():
        if raise_on_enter:
            raise RuntimeError("DB unavailable")
        conn = MagicMock()
        cursor = MagicMock()
        cursor.execute.side_effect = lambda q, p=(): executed.append((q, p))
        cursor.fetchone.return_value = row
        cursor_cm = MagicMock()
        cursor_cm.__enter__ = MagicMock(return_value=cursor)
        cursor_cm.__exit__ = MagicMock(return_value=None)
        conn.cursor.return_value = cursor_cm
        yield conn

    factory.executed = executed
    return factory


class TestESLContentSafety:
    """Tests for EthicalSafeguardLayer.check_content_safety (V2 relevance integration)."""

    @pytest.mark.asyncio
    async def test_content_safety_approves_safe_content(self, mock_context_manager):
        mock_context_manager.get_user_values = AsyncMock(return_value=[])
        esl = EthicalSafeguardLayer(mock_context_manager)

        result = await esl.check_content_safety(
            content="Your team standup starts in 10 minutes",
            user_id="user-1",
        )

        assert result.blocked is False
        assert "passes" in result.reason.lower()
        assert result.violated_values == []

    @pytest.mark.asyncio
    async def test_content_safety_blocks_filtered_topic(self, mock_context_manager):
        """Content matching a user's topic filter should be blocked."""
        mock_context_manager.get_user_values = AsyncMock(
            return_value=[create_user_value(ValueType.TOPIC_FILTER, "no_politics")]
        )
        esl = EthicalSafeguardLayer(mock_context_manager)

        result = await esl.check_content_safety(
            content="Breaking politics news roundup",
            user_id="user-2",
        )

        assert result.blocked is True
        assert "politics" in result.reason.lower()
        assert len(result.violated_values) == 1

    @pytest.mark.asyncio
    async def test_content_safety_blocks_manipulation(self, mock_context_manager):
        """Content with multiple manipulation patterns should be blocked."""
        mock_context_manager.get_user_values = AsyncMock(return_value=[])
        esl = EthicalSafeguardLayer(mock_context_manager)

        result = await esl.check_content_safety(
            content="Limited time offer — act now! Don't miss out!",
            user_id="user-3",
        )

        assert result.blocked is True
        assert "manipulation" in result.reason.lower()


class TestESLTransparencyReport:
    """Tests for EthicalSafeguardLayer.get_transparency_report."""

    @pytest.mark.asyncio
    async def test_empty_report_when_no_decisions(self, mock_context_manager):
        esl = EthicalSafeguardLayer(mock_context_manager)

        report = await esl.get_transparency_report("user-empty", days=7)

        assert report["total_decisions"] == 0
        assert report["approval_rate"] == 0.0
        assert report["vetoed_count"] == 0
        assert report["modified_count"] == 0
        assert "No decisions" in report["message"]

    @pytest.mark.asyncio
    async def test_report_aggregates_decisions(self, mock_context_manager):
        """Report should aggregate logged decisions and surface recent vetoes."""
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action()

        for _ in range(2):
            await esl.audit_logger.log_decision(
                "report-user",
                action,
                ESLDecision(
                    status=ESLDecisionStatus.APPROVED, reason="ok", confidence=0.95
                ),
                {},
            )
        await esl.audit_logger.log_decision(
            "report-user",
            action,
            ESLDecision(
                status=ESLDecisionStatus.MODIFIED,
                reason="delayed until morning",
                confidence=0.9,
            ),
            {},
        )
        await esl.audit_logger.log_decision(
            "report-user",
            action,
            ESLDecision(
                status=ESLDecisionStatus.VETOED,
                reason="focus mode",
                confidence=0.95,
            ),
            {},
        )

        report = await esl.get_transparency_report("report-user", days=7)

        assert report["total_decisions"] == 4
        assert report["approved_count"] == 2
        assert report["modified_count"] == 1
        assert report["vetoed_count"] == 1
        assert report["approval_rate"] == 0.5
        assert len(report["recent_vetoes"]) == 1
        assert report["recent_vetoes"][0]["reason"] == "focus mode"


class TestESLUserSensitivity:
    """Tests for ESL user-sensitivity persistence (note/_get_user_sensitivity)."""

    @pytest.mark.asyncio
    async def test_note_sensitivity_inserts_row(self, mock_context_manager):
        factory = _make_sensitivity_db_factory()
        esl = EthicalSafeguardLayer(mock_context_manager)

        with patch("utils.db.get_db_connection", factory):
            await esl.note_user_sensitivity("u-1", "work_summary", increment=0.2)

        assert len(factory.executed) == 1
        query, params = factory.executed[0]
        assert "INSERT INTO user_esl_sensitivity" in query
        assert params[0] == "u-1"
        assert params[1] == "work_summary"
        assert params[2] == 0.2
        assert params[3] == 0.2

    @pytest.mark.asyncio
    async def test_note_sensitivity_swallows_db_exception(self, mock_context_manager):
        failing = _make_sensitivity_db_factory(raise_on_enter=True)
        esl = EthicalSafeguardLayer(mock_context_manager)

        with patch("utils.db.get_db_connection", failing):
            # Should not raise — method logs and returns None
            await esl.note_user_sensitivity("u-2", "notification")

    @pytest.mark.asyncio
    async def test_get_sensitivity_returns_row_value(self, mock_context_manager):
        factory = _make_sensitivity_db_factory(row={"sensitivity_boost": 0.55})
        esl = EthicalSafeguardLayer(mock_context_manager)

        with patch("utils.db.get_db_connection", factory):
            boost = await esl._get_user_sensitivity("u-3", "work_summary")

        assert boost == 0.55
        assert len(factory.executed) == 1
        assert "SELECT sensitivity_boost" in factory.executed[0][0]

    @pytest.mark.asyncio
    async def test_get_sensitivity_returns_zero_when_no_row(self, mock_context_manager):
        factory = _make_sensitivity_db_factory(row=None)
        esl = EthicalSafeguardLayer(mock_context_manager)

        with patch("utils.db.get_db_connection", factory):
            boost = await esl._get_user_sensitivity("u-4", "work_summary")

        assert boost == 0.0

    @pytest.mark.asyncio
    async def test_get_sensitivity_returns_zero_on_exception(
        self, mock_context_manager
    ):
        failing = _make_sensitivity_db_factory(raise_on_enter=True)
        esl = EthicalSafeguardLayer(mock_context_manager)

        with patch("utils.db.get_db_connection", failing):
            boost = await esl._get_user_sensitivity("u-5", "work_summary")

        assert boost == 0.0


class TestESLEngineEvaluateActionBranches:
    """Cover evaluate_action branches not hit by the primary integration tests."""

    @pytest.mark.asyncio
    async def test_vetoes_non_chat_engagement_optimization(self, mock_context_manager):
        """Push notification with ≥4 engagement metrics should be vetoed."""
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(
            action_type=ActionType.PUSH_NOTIFICATION,
            content="check the app",
            metadata={
                "click_rate": 0.2,
                "time_in_app": 300,
                "daily_active": True,
                "session_length": 600,
            },
        )

        decision = await esl.evaluate_action(action, "engage-user")

        assert decision.status == ESLDecisionStatus.VETOED
        assert "EngagementDetector" in decision.applied_rules

    @pytest.mark.asyncio
    async def test_topic_filter_veto_populates_violated_values(
        self, mock_context_manager
    ):
        """Topic filter veto (hard-veto path) should list the violated value."""
        mock_context_manager.get_user_context = AsyncMock(
            return_value=UserContext(
                user_id="topic-user",
                current_time=datetime(2025, 1, 15, 12, 0),
                focus_mode=False,
                active_goals=[],
                user_values=[create_user_value(ValueType.TOPIC_FILTER, "no_politics")],
            )
        )
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(
            action_type=ActionType.CHAT_RESPONSE,
            content="Latest politics update from Washington",
        )

        decision = await esl.evaluate_action(action, "topic-user")

        # Topic filter is a *hard* veto — wins even in advisory mode.
        assert decision.status == ESLDecisionStatus.VETOED
        assert "TopicFilter" in decision.applied_rules
        assert len(decision.violated_values) == 1

    @pytest.mark.asyncio
    async def test_semantic_manipulation_llm_veto(self, mock_context_manager):
        """LLM flagging semantic manipulation should veto non-advisory actions."""
        # Regex-based manipulation_check must pass first (len > 100, no double pattern).
        long_content = (
            "Here is a considered update about the project, framed in an open "
            "and neutral way to give you the relevant context you need."
        )
        assert len(long_content) > 100

        llm = MagicMock()
        llm_response = MagicMock()
        llm_response.content = "YES"
        llm.ainvoke = AsyncMock(return_value=llm_response)

        esl = EthicalSafeguardLayer(mock_context_manager, llm=llm)
        action = create_action(
            action_type=ActionType.PUSH_NOTIFICATION, content=long_content
        )

        decision = await esl.evaluate_action(action, "llm-user")

        assert llm.ainvoke.await_count == 1
        assert decision.status == ESLDecisionStatus.VETOED
        assert "SemanticManipulationDetector" in decision.applied_rules

    @pytest.mark.asyncio
    async def test_semantic_manipulation_llm_exception_is_ignored(
        self, mock_context_manager
    ):
        """If the LLM raises, the semantic check is skipped silently."""
        long_content = (
            "Another longer piece of content that pushes past the 100-char "
            "threshold required to invoke the semantic check path entirely."
        )
        # Force a distinct hash from the YES test so the cache doesn't short-circuit.
        long_content = long_content + " — raises path"
        assert len(long_content) > 100

        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        esl = EthicalSafeguardLayer(mock_context_manager, llm=llm)
        action = create_action(
            action_type=ActionType.CHAT_RESPONSE, content=long_content
        )

        decision = await esl.evaluate_action(action, "llm-err-user")

        # With no other violations, the request should still be approved.
        assert decision.status == ESLDecisionStatus.APPROVED
        assert "SemanticManipulationDetector" not in decision.applied_rules

    @pytest.mark.asyncio
    async def test_time_suggested_modification_returns_modified(
        self, mock_context_manager
    ):
        """When time rule returns a suggested modification, decision is MODIFIED."""
        from esl.rules import RuleCheckResult

        esl = EthicalSafeguardLayer(mock_context_manager)
        replacement = create_action(content="Deferred to morning")
        esl.time_rules.check_boundaries = MagicMock(
            return_value=RuleCheckResult(
                passed=True,
                reason="Queued until working hours",
                suggested_modification=replacement,
            )
        )

        decision = await esl.evaluate_action(create_action(), "time-user")

        assert decision.status == ESLDecisionStatus.MODIFIED
        assert decision.modified_action is replacement
        assert decision.reason == "Queued until working hours"


# ==================== ESL Tool Gate Tests ====================


def _make_tool_gate_db(row=None, raise_on_enter=False):
    """Patchable factory for `utils.db.get_db_connection` used by ESLToolGate.

    Captures executed queries on `.executed` for inspection.
    """
    executed = []

    @contextmanager
    def factory():
        if raise_on_enter:
            raise RuntimeError("db down")
        conn = MagicMock()
        cursor = MagicMock()
        cursor.execute.side_effect = lambda q, p=(): executed.append((q, p))
        cursor.fetchone.return_value = row
        cursor_cm = MagicMock()
        cursor_cm.__enter__ = MagicMock(return_value=cursor)
        cursor_cm.__exit__ = MagicMock(return_value=None)
        conn.cursor.return_value = cursor_cm
        yield conn

    factory.executed = executed
    return factory


class TestESLToolGate:
    """End-to-end coverage of ESLToolGate.check and its DB helpers.

    These tests live alongside the broader ESL suite so `pytest tests/test_esl.py
    --cov=esl` exercises `esl/tool_gate.py` directly (the standalone
    `test_tool_gate.py` is run separately by the full suite).
    """

    @pytest.mark.asyncio
    async def test_low_risk_no_record_is_auto_approved(self):
        from esl.tool_gate import ESLToolGate, GateResult

        gate = ESLToolGate()
        with patch("esl.tool_gate.get_db_connection", _make_tool_gate_db(row=None)):
            result = await gate.check(
                user_id="u1",
                tool_id="notion",
                action_name="create_page",
                risk_level="low",
                preview="Create page",
            )

        assert result.status == GateResult.APPROVED
        assert result.reason == ""

    @pytest.mark.asyncio
    async def test_low_risk_explicit_allow_is_approved(self):
        from esl.tool_gate import ESLToolGate, GateResult

        gate = ESLToolGate()
        with patch(
            "esl.tool_gate.get_db_connection",
            _make_tool_gate_db(row={"trust_level": "allow"}),
        ):
            result = await gate.check(
                user_id="u1",
                tool_id="notion",
                action_name="create_page",
                risk_level="low",
                preview="Create page",
            )

        assert result.status == GateResult.APPROVED

    @pytest.mark.asyncio
    async def test_medium_risk_allow_is_approved(self):
        from esl.tool_gate import ESLToolGate, GateResult

        gate = ESLToolGate()
        with patch(
            "esl.tool_gate.get_db_connection",
            _make_tool_gate_db(row={"trust_level": "allow"}),
        ):
            result = await gate.check(
                user_id="u1",
                tool_id="github",
                action_name="create_issue",
                risk_level="medium",
                preview="Create issue",
            )

        assert result.status == GateResult.APPROVED

    @pytest.mark.asyncio
    async def test_medium_risk_no_record_requires_confirmation(self):
        from esl.tool_gate import ESLToolGate, GateResult

        gate = ESLToolGate()
        with patch("esl.tool_gate.get_db_connection", _make_tool_gate_db(row=None)):
            result = await gate.check(
                user_id="u1",
                tool_id="github",
                action_name="create_issue",
                risk_level="medium",
                preview="Create issue: Fix login",
            )

        assert result.status == GateResult.PENDING_CONFIRMATION
        assert "Fix login" in result.preview
        assert "First-time" in result.reason

    @pytest.mark.asyncio
    async def test_medium_risk_ask_trust_requires_confirmation(self):
        from esl.tool_gate import ESLToolGate, GateResult

        gate = ESLToolGate()
        with patch(
            "esl.tool_gate.get_db_connection",
            _make_tool_gate_db(row={"trust_level": "ask"}),
        ):
            result = await gate.check(
                user_id="u1",
                tool_id="github",
                action_name="create_issue",
                risk_level="medium",
                preview="Create issue",
            )

        assert result.status == GateResult.PENDING_CONFIRMATION

    @pytest.mark.asyncio
    async def test_deny_trust_vetoes_medium_risk(self):
        from esl.tool_gate import ESLToolGate, GateResult

        gate = ESLToolGate()
        with patch(
            "esl.tool_gate.get_db_connection",
            _make_tool_gate_db(row={"trust_level": "deny"}),
        ):
            result = await gate.check(
                user_id="u1",
                tool_id="github",
                action_name="delete_repo",
                risk_level="medium",
                preview="Delete repo",
            )

        assert result.status == GateResult.VETOED
        assert "denied" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_high_risk_always_requires_confirmation(self):
        """High-risk actions confirm even with an existing 'allow' grant."""
        from esl.tool_gate import ESLToolGate, GateResult

        gate = ESLToolGate()
        with patch(
            "esl.tool_gate.get_db_connection",
            _make_tool_gate_db(row={"trust_level": "allow"}),
        ):
            result = await gate.check(
                user_id="u1",
                tool_id="gmail",
                action_name="send_reply",
                risk_level="high",
                preview="Send email to alice@example.com",
            )

        assert result.status == GateResult.PENDING_CONFIRMATION
        assert "High-risk" in result.reason

    @pytest.mark.asyncio
    async def test_db_exception_falls_back_to_confirmation(self):
        """If the permission lookup fails, default to asking the user."""
        from esl.tool_gate import ESLToolGate, GateResult

        gate = ESLToolGate()
        failing = _make_tool_gate_db(raise_on_enter=True)
        with patch("esl.tool_gate.get_db_connection", failing):
            result = await gate.check(
                user_id="u1",
                tool_id="github",
                action_name="create_issue",
                risk_level="medium",
                preview="Create issue",
            )

        assert result.status == GateResult.PENDING_CONFIRMATION
        assert "Gate check failed" in result.reason

    @pytest.mark.asyncio
    async def test_set_trust_issues_upsert(self):
        from esl.tool_gate import ESLToolGate

        gate = ESLToolGate()
        factory = _make_tool_gate_db()
        with patch("esl.tool_gate.get_db_connection", factory):
            await gate.set_trust(
                user_id="u1",
                tool_id="notion",
                action_name="create_page",
                trust_level="allow",
            )

        assert len(factory.executed) == 1
        query, params = factory.executed[0]
        assert "INSERT INTO tool_permissions" in query
        assert "ON CONFLICT" in query
        assert params == ("u1", "notion", "create_page", "allow")
