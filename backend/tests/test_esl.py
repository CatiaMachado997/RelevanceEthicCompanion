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
from datetime import datetime, UTC
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
    RuleCheckResult,
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
    cm.get_user_context = AsyncMock(return_value=UserContext(
        user_id="test-user-123",
        current_time=datetime.now(UTC),
        focus_mode=False,
        active_goals=["goal-1"],
        user_values=[],
    ))
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
    metadata: dict = None,
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
        values = [create_user_value(ValueType.BOUNDARY, "no_work_after_19h", active=False)]
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

    def test_detects_fomo_dont_miss_out(self, manipulation_detector):
        """Should detect 'don't miss out' FOMO pattern"""
        result = manipulation_detector.check_content(
            "Don't miss out on this opportunity!"
        )

        assert result.passed is False
        assert "FOMO" in result.reason

    def test_detects_fomo_last_chance(self, manipulation_detector):
        """Should detect 'last chance' FOMO pattern"""
        result = manipulation_detector.check_content(
            "This is your last chance to respond!"
        )

        assert result.passed is False
        assert "FOMO" in result.reason

    def test_detects_fomo_limited_time(self, manipulation_detector):
        """Should detect 'limited time' FOMO pattern"""
        result = manipulation_detector.check_content(
            "Limited time offer - act now!"
        )

        assert result.passed is False
        assert "FOMO" in result.reason

    def test_detects_artificial_urgency(self, manipulation_detector):
        """Should detect artificial urgency"""
        result = manipulation_detector.check_content(
            "You must act immediately to avoid problems!"
        )

        assert result.passed is False
        assert "urgency" in result.reason.lower()

    def test_allows_genuine_urgent_meeting(self, manipulation_detector):
        """Should allow genuine urgent meeting notifications"""
        result = manipulation_detector.check_content(
            "Urgent meeting scheduled for 3 PM"
        )

        # The regex explicitly excludes "urgent meeting"
        assert result.passed is True

    def test_detects_guilt_tripping(self, manipulation_detector):
        """Should detect guilt-tripping patterns"""
        result = manipulation_detector.check_content(
            "You should have responded earlier."
        )

        assert result.passed is False
        assert "guilt" in result.reason.lower()

    def test_detects_guilt_forgot(self, manipulation_detector):
        """Should detect 'you forgot' guilt pattern"""
        result = manipulation_detector.check_content(
            "You forgot to complete this task!"
        )

        assert result.passed is False
        assert "guilt" in result.reason.lower()

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

    def test_blocks_click_rate_optimization(self, engagement_detector):
        """Actions optimizing for click rate should be blocked"""
        action = create_action(metadata={"click_rate": 0.15})

        result = engagement_detector.check_intent(action)

        assert result.passed is False
        assert "click_rate" in result.reason

    def test_blocks_time_in_app_optimization(self, engagement_detector):
        """Actions optimizing for time in app should be blocked"""
        action = create_action(metadata={"time_in_app": 300})

        result = engagement_detector.check_intent(action)

        assert result.passed is False
        assert "time_in_app" in result.reason

    def test_blocks_retention_boost(self, engagement_detector):
        """Actions optimizing for retention should be blocked"""
        action = create_action(metadata={"retention_boost": True})

        result = engagement_detector.check_intent(action)

        assert result.passed is False
        assert "retention_boost" in result.reason

    def test_blocks_critical_without_assistance_intent(self, engagement_detector):
        """Critical urgency without assistance intent should be suspicious"""
        action = create_action(urgency=UrgencyLevel.CRITICAL, metadata={})

        result = engagement_detector.check_intent(action)

        assert result.passed is False
        assert "manipulation" in result.reason.lower()

    def test_allows_critical_with_user_request(self, engagement_detector):
        """Critical urgency with user request should pass"""
        action = create_action(
            urgency=UrgencyLevel.CRITICAL,
            metadata={"user_request": True}
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
        values = [create_user_value(ValueType.TOPIC_FILTER, "no_politics", active=False)]

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
        """Actions with manipulation should be vetoed"""
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(content="Don't miss out on this limited time offer!")

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.VETOED
        assert "FOMO" in decision.reason or "manipulation" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_vetoes_focus_mode_violation(self, mock_context_manager):
        """Non-critical actions during focus mode should be vetoed"""
        mock_context_manager.get_user_context = AsyncMock(return_value=UserContext(
            user_id="test-user",
            current_time=datetime.now(UTC),
            focus_mode=True,  # Focus mode enabled
            active_goals=[],
            user_values=[],
        ))
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(urgency=UrgencyLevel.LOW)

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.VETOED
        assert "focus mode" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_allows_critical_during_focus_mode(self, mock_context_manager):
        """Critical actions should be allowed even during focus mode"""
        mock_context_manager.get_user_context = AsyncMock(return_value=UserContext(
            user_id="test-user",
            current_time=datetime.now(UTC),
            focus_mode=True,
            active_goals=[],
            user_values=[],
        ))
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(
            urgency=UrgencyLevel.CRITICAL,
            metadata={"user_request": True}  # Has assistance intent
        )

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.APPROVED

    @pytest.mark.asyncio
    async def test_vetoes_time_boundary_violation(self, mock_context_manager):
        """Actions violating time boundaries should be vetoed"""
        mock_context_manager.get_user_context = AsyncMock(return_value=UserContext(
            user_id="test-user",
            current_time=datetime(2025, 1, 15, 21, 0),  # 9 PM
            focus_mode=False,
            active_goals=[],
            user_values=[
                create_user_value(ValueType.BOUNDARY, "no_work_after_19h")
            ],
        ))
        esl = EthicalSafeguardLayer(mock_context_manager)
        action = create_action(content_type="work_summary")

        decision = await esl.evaluate_action(action, "test-user")

        assert decision.status == ESLDecisionStatus.VETOED
        assert len(decision.violated_values) > 0

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
            context_snapshot={"test": True}
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
            "test-user", action,
            ESLDecision(status=ESLDecisionStatus.APPROVED, reason="ok", confidence=0.9),
            {}
        )
        await audit_logger.log_decision(
            "test-user", action,
            ESLDecision(status=ESLDecisionStatus.VETOED, reason="blocked", confidence=0.9),
            {}
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
                "test-user", action,
                ESLDecision(status=ESLDecisionStatus.APPROVED, reason="ok", confidence=0.9),
                {}
            )
        await audit_logger.log_decision(
            "test-user", action,
            ESLDecision(status=ESLDecisionStatus.VETOED, reason="blocked", confidence=0.9),
            {}
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
            "user-1", action,
            ESLDecision(status=ESLDecisionStatus.APPROVED, reason="ok", confidence=0.9),
            {}
        )
        await audit_logger.log_decision(
            "user-2", action,
            ESLDecision(status=ESLDecisionStatus.VETOED, reason="blocked", confidence=0.9),
            {}
        )

        user1_logs = await audit_logger.get_user_logs("user-1", days=1)
        user2_logs = await audit_logger.get_user_logs("user-2", days=1)

        assert len(user1_logs) == 1
        assert len(user2_logs) == 1
        assert user1_logs[0].decision.status == ESLDecisionStatus.APPROVED
        assert user2_logs[0].decision.status == ESLDecisionStatus.VETOED
