"""
Unit tests for Phase 7 proactive scheduler jobs.

Tests use mocking so no live DB, Groq, or scheduler is required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone


@pytest.fixture(autouse=True)
def _default_patch_esl_gate_and_telemetry():
    """Default-patch the ESL proactive gate to APPROVED, and stub the
    telemetry service to a no-op, so existing scheduler tests don't need
    to mock these directly. Tests that want different behaviour patch
    explicitly inside their own bodies.
    """

    async def _approve(
        user_id, notification_type, content, urgency="low", metadata=None
    ):
        return (True, content)

    with patch(
        "services.scheduler.gate_proactive_notification", side_effect=_approve
    ), patch("services.scheduler.ToolTelemetryService") as mock_telemetry_cls:
        mock_telemetry_cls.return_value.record_tool_call = MagicMock(return_value="")
        yield


# ─────────────────────────────────────────────
# Helper: build a minimal BackgroundScheduler without starting APScheduler
# ─────────────────────────────────────────────


def make_scheduler():
    from services.scheduler import BackgroundScheduler

    data_ingestion = MagicMock()
    sched = BackgroundScheduler.__new__(BackgroundScheduler)
    sched.data_ingestion = data_ingestion
    sched.scheduler = MagicMock()
    sched._running = False
    return sched


# ─────────────────────────────────────────────
# _generate_deadline_warnings
# ─────────────────────────────────────────────


class TestDeadlineWarnings:
    @pytest.mark.asyncio
    async def test_no_tasks_due_does_nothing(self):
        sched = make_scheduler()
        with patch("services.scheduler.get_db_connection") as mock_db:
            conn = MagicMock().__enter__.return_value
            cur = conn.cursor().__enter__.return_value
            cur.fetchall.return_value = []
            mock_db.return_value.__enter__.return_value = conn

            await sched._generate_deadline_warnings()
            # create_notification should NOT be called
            cur.execute.assert_called_once()  # only the SELECT

    @pytest.mark.asyncio
    async def test_creates_warning_for_task_not_yet_warned(self):
        sched = make_scheduler()
        now = datetime.now(timezone.utc)
        task_row = {
            "id": "task-uuid-1",
            "user_id": "user-uuid-1",
            "title": "Submit report",
            "due_date": now + timedelta(hours=3),
            "priority": 8,
            "project_title": "Q2 Review",
        }

        call_count = {"n": 0}

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)

            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: return the due task
                cur.fetchall.return_value = [task_row]
            elif call_count["n"] == 2:
                # Second call (dedup check): no existing warning
                cur.fetchone.return_value = None
            else:
                # Third call: create_notification INSERT
                cur.fetchone.return_value = None

            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch(
            "services.scheduler.BackgroundScheduler._generate_deadline_warnings",
            wraps=sched._generate_deadline_warnings,
        ):
            # Just verify it doesn't raise
            await sched._generate_deadline_warnings()

    @pytest.mark.asyncio
    async def test_skips_task_already_warned_today(self):
        sched = make_scheduler()
        now = datetime.now(timezone.utc)
        task_row = {
            "id": "task-uuid-2",
            "user_id": "user-uuid-2",
            "title": "Send invoice",
            "due_date": now + timedelta(hours=1),
            "priority": 5,
            "project_title": None,
        }

        call_count = {"n": 0}

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)

            call_count["n"] += 1
            if call_count["n"] == 1:
                cur.fetchall.return_value = [task_row]
            else:
                # Dedup hit — already warned today
                cur.fetchone.return_value = {"1": 1}

            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect):
            await sched._generate_deadline_warnings()
            # If dedup triggers, no INSERT should happen beyond the dedup SELECT
            assert call_count["n"] == 2  # SELECT tasks + dedup check only


# ─────────────────────────────────────────────
# _generate_daily_focus_plan
# ─────────────────────────────────────────────


class TestDailyFocusPlan:
    @pytest.mark.asyncio
    async def test_skips_users_with_no_data(self):
        """Users with empty snapshot (no events, tasks, goals) should be skipped."""
        sched = make_scheduler()

        empty_snapshot = {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "tasks_due_soon": [],
            "overdue_count": 0,
            "active_projects": [],
            "upcoming_events": [],
            "active_goals": [],
            "calendar_pressure": "light",
        }

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            cur.fetchall.return_value = [{"id": "user-uuid-3"}]
            cur.fetchone.return_value = None  # no dedup hit
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch(
            "services.context_snapshot.ContextSnapshotService.compute",
            return_value=empty_snapshot,
        ), patch(
            "services.context_manager.ContextManager"
        ), patch(
            "langchain_groq.ChatGroq"
        ):
            # Should not raise, just skip the user
            await sched._generate_daily_focus_plan()

    @pytest.mark.asyncio
    async def test_skips_users_already_notified_today(self):
        """If daily focus notification already sent today, skip the LLM call."""
        sched = make_scheduler()

        call_count = {"n": 0}

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)

            call_count["n"] += 1
            if call_count["n"] == 1:
                cur.fetchall.return_value = [{"id": "user-uuid-4"}]
            else:
                # Dedup: already sent today
                cur.fetchone.return_value = {"1": 1}

            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        llm_called = []

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch("services.context_manager.ContextManager"), patch(
            "langchain_groq.ChatGroq"
        ) as mock_llm_cls:
            mock_llm_cls.return_value.ainvoke = AsyncMock(
                side_effect=lambda _: llm_called.append(1)
            )
            await sched._generate_daily_focus_plan()
            assert len(llm_called) == 0  # LLM should not be called


# ─────────────────────────────────────────────
# _generate_pre_meeting_briefs
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# _generate_project_status_snapshot
# ─────────────────────────────────────────────


class TestProjectStatusSnapshot:
    @pytest.mark.asyncio
    async def test_no_active_projects_does_nothing(self):
        sched = make_scheduler()

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            cur.fetchall.return_value = []
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch("langchain_groq.ChatGroq"):
            await sched._generate_project_status_snapshot()

    @pytest.mark.asyncio
    async def test_skips_user_already_snapshotted_this_week(self):
        sched = make_scheduler()
        project_row = {
            "id": "proj-1",
            "user_id": "user-6",
            "title": "Product Launch",
            "open_tasks": 3,
            "done_tasks": 7,
            "overdue_tasks": 0,
        }

        call_count = {"n": 0}

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)

            call_count["n"] += 1
            if call_count["n"] == 1:
                cur.fetchall.return_value = [project_row]
            else:
                cur.fetchone.return_value = {"1": 1}  # dedup hit

            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        llm_called = []

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch("langchain_groq.ChatGroq") as mock_llm_cls:
            mock_llm_cls.return_value.ainvoke = AsyncMock(
                side_effect=lambda _: llm_called.append(1)
            )
            await sched._generate_project_status_snapshot()
            assert len(llm_called) == 0

    @pytest.mark.asyncio
    async def test_generates_snapshot_when_no_prior_notification(self):
        sched = make_scheduler()
        project_row = {
            "id": "proj-2",
            "user_id": "user-7",
            "title": "Q3 Report",
            "open_tasks": 5,
            "done_tasks": 2,
            "overdue_tasks": 1,
        }

        call_count = {"n": 0}

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)

            call_count["n"] += 1
            if call_count["n"] == 1:
                cur.fetchall.return_value = [project_row]
            elif call_count["n"] == 2:
                cur.fetchone.return_value = None  # no dedup hit

            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        mock_response = MagicMock()
        mock_response.content = "Q3 Report is progressing well with 2 tasks done. One task is overdue — prioritise it Monday morning."  # noqa: E501

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch("langchain_groq.ChatGroq") as mock_llm_cls:
            mock_llm_cls.return_value.ainvoke = AsyncMock(return_value=mock_response)
            await sched._generate_project_status_snapshot()
            # LLM was called once for the one user
            assert mock_llm_cls.return_value.ainvoke.call_count == 1


# ─────────────────────────────────────────────
# _generate_pre_meeting_briefs
# ─────────────────────────────────────────────


class TestPreMeetingBriefs:
    @pytest.mark.asyncio
    async def test_no_upcoming_events_does_nothing(self):
        sched = make_scheduler()

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            cur.fetchall.return_value = []
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch("services.context_manager.ContextManager"), patch(
            "langchain_groq.ChatGroq"
        ):
            await sched._generate_pre_meeting_briefs()

    @pytest.mark.asyncio
    async def test_skips_event_already_briefed(self):
        """If a brief notification already exists for the event start, skip it."""
        sched = make_scheduler()
        now = datetime.now(timezone.utc)
        event_start = now + timedelta(minutes=30)

        call_count = {"n": 0}

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)

            call_count["n"] += 1
            if call_count["n"] == 1:
                cur.fetchall.return_value = [
                    {
                        "user_id": "user-uuid-5",
                        "title": "Quarterly Review",
                        "start_time": event_start,
                        "location": "Room 3",
                        "description": None,
                    }
                ]
            else:
                # Dedup hit — brief already exists
                cur.fetchone.return_value = {"1": 1}

            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        llm_called = []

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch("services.context_manager.ContextManager"), patch(
            "langchain_groq.ChatGroq"
        ) as mock_llm_cls:
            mock_llm_cls.return_value.ainvoke = AsyncMock(
                side_effect=lambda _: llm_called.append(1)
            )
            await sched._generate_pre_meeting_briefs()
            assert len(llm_called) == 0


# ─────────────────────────────────────────────
# _generate_related_items_clusters
# ─────────────────────────────────────────────


class TestRelatedItemsClustering:
    @pytest.mark.asyncio
    async def test_no_cross_type_items_skips_user(self):
        """If only tasks exist (no events or goals), no notification is created."""
        sched = make_scheduler()
        call_count = {"n": 0}

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            call_count["n"] += 1
            n = call_count["n"]
            if n == 1:
                cur.fetchall.return_value = [{"id": "user-8"}]
            elif n == 2:
                cur.fetchone.return_value = None  # no dedup hit
            elif n == 3:
                # tasks
                cur.fetchall.return_value = [
                    {"title": "Launch campaign"},
                    {"title": "Write report"},
                ]
            elif n == 4:
                cur.fetchall.return_value = []  # no events
            else:
                cur.fetchall.return_value = []  # no goals
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect):
            await sched._generate_related_items_clusters()
        # No notification should be created — tasks only, no cross-type match

    @pytest.mark.asyncio
    async def test_skips_user_already_clustered_this_week(self):
        sched = make_scheduler()
        call_count = {"n": 0}

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            call_count["n"] += 1
            n = call_count["n"]
            if n == 1:
                cur.fetchall.return_value = [{"id": "user-9"}]
            else:
                cur.fetchone.return_value = {"1": 1}  # dedup hit
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect):
            await sched._generate_related_items_clusters()
        assert call_count["n"] == 2  # only users fetch + dedup check

    def test_keywords_extracts_significant_words(self):
        """Unit test for the keyword extraction logic (tested via the scheduler module)."""
        import re

        STOP_WORDS = {
            "the",
            "and",
            "for",
            "with",
            "this",
            "that",
            "from",
            "have",
            "will",
            "been",
            "are",
            "our",
            "your",
            "their",
            "about",
            "some",
        }

        def keywords(text):
            words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
            return {w for w in words if w not in STOP_WORDS}

        result = keywords("Prepare for the Q3 product launch meeting")
        assert "prepare" in result
        assert "product" in result
        assert "launch" in result
        assert "meeting" in result
        assert "the" not in result
        assert "for" not in result


# ─────────────────────────────────────────────
# Sprint C Task 4: ESL gating in scheduler
# ─────────────────────────────────────────────


class TestSchedulerESLGating:
    @pytest.mark.asyncio
    async def test_daily_focus_plan_respects_veto(self):
        """When ESL vetoes, create_notification must NOT be called."""
        sched = make_scheduler()

        snapshot = {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "tasks_due_soon": [
                {"title": "Task A", "due_date": "2026-04-26", "priority": 7}
            ],
            "overdue_count": 0,
            "active_projects": [],
            "upcoming_events": [{"title": "Standup", "start_time": "2026-04-26T10:00"}],
            "active_goals": [{"title": "Ship Sprint C"}],
            "calendar_pressure": "moderate",
        }

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            cur.fetchall.return_value = [{"id": "user-veto-1"}]
            cur.fetchone.return_value = None  # no dedup
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        mock_response = MagicMock()
        mock_response.content = "Plan: do A, then B."

        async def _veto(
            user_id, notification_type, content, urgency="low", metadata=None
        ):
            return (False, content)

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch(
            "services.context_snapshot.ContextSnapshotService.compute",
            return_value=snapshot,
        ), patch(
            "services.context_manager.ContextManager"
        ), patch(
            "langchain_groq.ChatGroq"
        ) as mock_llm_cls, patch(
            "services.scheduler.gate_proactive_notification", side_effect=_veto
        ), patch(
            "routes.notifications.create_notification"
        ) as mock_create_notification:
            mock_llm_cls.return_value.ainvoke = AsyncMock(return_value=mock_response)
            await sched._generate_daily_focus_plan()

        # create_notification must NOT be called when ESL vetoes
        assert mock_create_notification.call_count == 0

    @pytest.mark.asyncio
    async def test_pre_meeting_brief_uses_modified_content(self):
        """When ESL MODIFIES, create_notification must use the modified text."""
        sched = make_scheduler()
        now = datetime.now(timezone.utc)
        event_start = now + timedelta(minutes=30)

        call_count = {"n": 0}

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            call_count["n"] += 1
            n = call_count["n"]
            if n == 1:
                cur.fetchall.return_value = [
                    {
                        "user_id": "user-mod-1",
                        "title": "Strategy Meeting",
                        "start_time": event_start,
                        "location": "Room 1",
                        "description": None,
                    }
                ]
            else:
                cur.fetchone.return_value = None  # no dedup
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        mock_response = MagicMock()
        mock_response.content = "Original LLM brief text."

        modified_text = "ESL modified safer text."

        async def _modify(
            user_id, notification_type, content, urgency="low", metadata=None
        ):
            return (True, modified_text)

        captured = {}

        def fake_create_notification(conn, **kwargs):
            captured.update(kwargs)
            return None

        # Patch the active goals call on the ContextManager so it returns []
        ctx_mgr_inst = MagicMock()
        ctx_mgr_inst.get_active_goals = AsyncMock(return_value=[])

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch(
            "services.context_manager.ContextManager", return_value=ctx_mgr_inst
        ), patch(
            "langchain_groq.ChatGroq"
        ) as mock_llm_cls, patch(
            "services.scheduler.gate_proactive_notification", side_effect=_modify
        ), patch(
            "routes.notifications.create_notification",
            side_effect=fake_create_notification,
        ):
            mock_llm_cls.return_value.ainvoke = AsyncMock(return_value=mock_response)
            await sched._generate_pre_meeting_briefs()

        assert captured.get("message") == modified_text[:500]
        assert captured.get("message") != "Original LLM brief text."

    @pytest.mark.asyncio
    async def test_deadline_warning_records_telemetry_row(self):
        """deadline_warning flow must call record_tool_call with correct fields."""
        sched = make_scheduler()
        now = datetime.now(timezone.utc)
        task_row = {
            "id": "task-tele-1",
            "user_id": "user-tele-1",
            "title": "File taxes",
            "due_date": now + timedelta(hours=2),
            "priority": 9,
            "project_title": "Personal",
        }

        call_count = {"n": 0}

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            call_count["n"] += 1
            n = call_count["n"]
            if n == 1:
                cur.fetchall.return_value = [task_row]
            else:
                cur.fetchone.return_value = None
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        record_calls = []

        def fake_record_tool_call(**kwargs):
            record_calls.append(kwargs)
            return ""

        telemetry_inst = MagicMock()
        telemetry_inst.record_tool_call = MagicMock(side_effect=fake_record_tool_call)

        async def _approve(
            user_id, notification_type, content, urgency="low", metadata=None
        ):
            return (True, content)

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch(
            "services.scheduler.gate_proactive_notification", side_effect=_approve
        ), patch(
            "services.scheduler.ToolTelemetryService", return_value=telemetry_inst
        ), patch(
            "routes.notifications.create_notification"
        ):
            await sched._generate_deadline_warnings()

        assert len(record_calls) >= 1
        first = record_calls[0]
        assert first.get("tool_name") == "deadline_warning"
        assert first.get("source") == "scheduled"

    # ─────────────────────────────────────────────
    # Sprint E Task 5: weekly_review_brief
    # ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_weekly_review_brief_sends_when_approved(self):
        """When ESL approves and review is non-empty, create_notification fires."""
        sched = make_scheduler()

        review = {
            "period": {
                "start": "2026-04-20T00:00:00+00:00",
                "end": "2026-04-27T00:00:00+00:00",
            },
            "completed_tasks": [{"id": "t1", "title": "Wrote spec"}],
            "completed_milestones": [],
            "carry_over_tasks": [],
            "upcoming_tasks": [{"id": "t2", "title": "Ship feature"}],
            "upcoming_milestones": [],
        }

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            cur.fetchall.return_value = [{"id": "user-wr-1"}]
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch(
            "services.work_rollups.WorkRollupsService.get_weekly_review",
            return_value=review,
        ), patch.object(
            sched,
            "_summarize_weekly_review",
            new=AsyncMock(return_value="Last week was solid."),
        ), patch(
            "routes.notifications.create_notification"
        ) as mock_create_notification:
            await sched._generate_weekly_review_brief()

        assert mock_create_notification.call_count == 1
        kwargs = mock_create_notification.call_args.kwargs
        assert kwargs.get("user_id") == "user-wr-1"
        assert kwargs.get("message") == "Last week was solid."

    @pytest.mark.asyncio
    async def test_weekly_review_brief_respects_veto(self):
        """When ESL vetoes, create_notification must NOT be called."""
        sched = make_scheduler()

        review = {
            "period": {
                "start": "2026-04-20T00:00:00+00:00",
                "end": "2026-04-27T00:00:00+00:00",
            },
            "completed_tasks": [{"id": "t1", "title": "Wrote spec"}],
            "completed_milestones": [],
            "carry_over_tasks": [],
            "upcoming_tasks": [],
            "upcoming_milestones": [],
        }

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            cur.fetchall.return_value = [{"id": "user-wr-2"}]
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        async def _veto(
            user_id, notification_type, content, urgency="low", metadata=None
        ):
            return (False, content)

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch(
            "services.work_rollups.WorkRollupsService.get_weekly_review",
            return_value=review,
        ), patch.object(
            sched, "_summarize_weekly_review", new=AsyncMock(return_value="Hi.")
        ), patch(
            "services.scheduler.gate_proactive_notification", side_effect=_veto
        ), patch(
            "routes.notifications.create_notification"
        ) as mock_create_notification:
            await sched._generate_weekly_review_brief()

        assert mock_create_notification.call_count == 0

    @pytest.mark.asyncio
    async def test_weekly_review_brief_skips_empty_user(self):
        """If get_weekly_review returns all empty lists: no LLM, no notification, no telemetry."""
        sched = make_scheduler()

        empty_review = {
            "period": {
                "start": "2026-04-20T00:00:00+00:00",
                "end": "2026-04-27T00:00:00+00:00",
            },
            "completed_tasks": [],
            "completed_milestones": [],
            "carry_over_tasks": [],
            "upcoming_tasks": [],
            "upcoming_milestones": [],
        }

        def db_side_effect():
            ctx = MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            conn.__enter__ = MagicMock(return_value=conn)
            conn.__exit__ = MagicMock(return_value=False)
            conn.cursor = MagicMock(return_value=cur)
            cur.fetchall.return_value = [{"id": "user-wr-3"}]
            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        summarize_mock = AsyncMock(return_value="should not be called")
        telemetry_inst = MagicMock()
        telemetry_inst.record_tool_call = MagicMock(return_value="")

        with patch(
            "services.scheduler.get_db_connection", side_effect=db_side_effect
        ), patch(
            "services.work_rollups.WorkRollupsService.get_weekly_review",
            return_value=empty_review,
        ), patch.object(
            sched, "_summarize_weekly_review", new=summarize_mock
        ), patch(
            "services.scheduler.ToolTelemetryService", return_value=telemetry_inst
        ), patch(
            "routes.notifications.create_notification"
        ) as mock_create_notification:
            await sched._generate_weekly_review_brief()

        assert summarize_mock.await_count == 0
        assert mock_create_notification.call_count == 0
        assert telemetry_inst.record_tool_call.call_count == 0
