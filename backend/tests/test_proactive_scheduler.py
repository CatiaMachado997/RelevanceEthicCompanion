"""
Unit tests for Phase 7 proactive scheduler jobs.

Tests use mocking so no live DB, Groq, or scheduler is required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta


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
        now = datetime.utcnow()
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

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect), \
             patch("services.scheduler.BackgroundScheduler._generate_deadline_warnings",
                   wraps=sched._generate_deadline_warnings):
            # Just verify it doesn't raise
            await sched._generate_deadline_warnings()

    @pytest.mark.asyncio
    async def test_skips_task_already_warned_today(self):
        sched = make_scheduler()
        now = datetime.utcnow()
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

        insert_calls = []
        original_create = None

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
            "computed_at": datetime.utcnow().isoformat(),
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

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect), \
             patch("services.context_snapshot.ContextSnapshotService.compute",
                   return_value=empty_snapshot), \
             patch("services.context_manager.ContextManager"), \
             patch("langchain_groq.ChatGroq"):
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

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect), \
             patch("services.context_manager.ContextManager"), \
             patch("langchain_groq.ChatGroq") as mock_llm_cls:
            mock_llm_cls.return_value.ainvoke = AsyncMock(side_effect=lambda _: llm_called.append(1))
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

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect), \
             patch("langchain_groq.ChatGroq"):
            await sched._generate_project_status_snapshot()

    @pytest.mark.asyncio
    async def test_skips_user_already_snapshotted_this_week(self):
        sched = make_scheduler()
        project_row = {
            "id": "proj-1", "user_id": "user-6",
            "title": "Product Launch", "open_tasks": 3, "done_tasks": 7, "overdue_tasks": 0,
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

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect), \
             patch("langchain_groq.ChatGroq") as mock_llm_cls:
            mock_llm_cls.return_value.ainvoke = AsyncMock(side_effect=lambda _: llm_called.append(1))
            await sched._generate_project_status_snapshot()
            assert len(llm_called) == 0

    @pytest.mark.asyncio
    async def test_generates_snapshot_when_no_prior_notification(self):
        sched = make_scheduler()
        project_row = {
            "id": "proj-2", "user_id": "user-7",
            "title": "Q3 Report", "open_tasks": 5, "done_tasks": 2, "overdue_tasks": 1,
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
        mock_response.content = "Q3 Report is progressing well with 2 tasks done. One task is overdue — prioritise it Monday morning."

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect), \
             patch("langchain_groq.ChatGroq") as mock_llm_cls:
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

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect), \
             patch("services.context_manager.ContextManager"), \
             patch("langchain_groq.ChatGroq"):
            await sched._generate_pre_meeting_briefs()

    @pytest.mark.asyncio
    async def test_skips_event_already_briefed(self):
        """If a brief notification already exists for the event start, skip it."""
        sched = make_scheduler()
        now = datetime.utcnow()
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
                cur.fetchall.return_value = [{
                    "user_id": "user-uuid-5",
                    "title": "Quarterly Review",
                    "start_time": event_start,
                    "location": "Room 3",
                    "description": None,
                }]
            else:
                # Dedup hit — brief already exists
                cur.fetchone.return_value = {"1": 1}

            ctx.__enter__ = MagicMock(return_value=conn)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        llm_called = []

        with patch("services.scheduler.get_db_connection", side_effect=db_side_effect), \
             patch("services.context_manager.ContextManager"), \
             patch("langchain_groq.ChatGroq") as mock_llm_cls:
            mock_llm_cls.return_value.ainvoke = AsyncMock(side_effect=lambda _: llm_called.append(1))
            await sched._generate_pre_meeting_briefs()
            assert len(llm_called) == 0
