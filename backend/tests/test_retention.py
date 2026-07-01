"""
Sprint E Task 1: tests for the daily telemetry prune job.

The job deletes rows older than RETENTION_DAYS (default 90) from
`tool_call_events` (filter on created_at) and `esl_audit_log` (filter on
timestamp). Tests use mocked DB cursors — no live Postgres needed.
"""

import pytest
from unittest.mock import MagicMock, patch


def make_scheduler():
    """Build a BackgroundScheduler instance without starting APScheduler."""
    from services.scheduler import BackgroundScheduler

    sched = BackgroundScheduler.__new__(BackgroundScheduler)
    sched.data_ingestion = MagicMock()
    sched.scheduler = MagicMock()
    sched._running = False
    return sched


def _build_db_mock(tool_rowcount=0, audit_rowcount=0):
    """Build a get_db_connection mock that records executed DELETEs."""
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)

    rowcounts = [tool_rowcount, audit_rowcount]

    def execute_side_effect(sql, params=None):
        cur.rowcount = rowcounts.pop(0) if rowcounts else 0

    cur.execute = MagicMock(side_effect=execute_side_effect)

    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor = MagicMock(return_value=cur)

    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=conn)
    ctx.__exit__ = MagicMock(return_value=False)

    return ctx, cur


class TestPruneOldTelemetry:
    @pytest.mark.asyncio
    async def test_prune_deletes_old_rows_default_90d(self):
        """Default RETENTION_DAYS=90 — both DELETEs run with parameter 90."""
        sched = make_scheduler()
        ctx, cur = _build_db_mock(tool_rowcount=12, audit_rowcount=4)

        with patch("services.scheduler.get_db_connection", return_value=ctx):
            await sched._prune_old_telemetry()

        # Two DELETEs: one per table
        assert cur.execute.call_count == 2

        first_sql, first_params = cur.execute.call_args_list[0].args
        second_sql, second_params = cur.execute.call_args_list[1].args

        assert "DELETE FROM tool_call_events" in first_sql
        assert "created_at" in first_sql
        assert first_params == (90,)

        assert "DELETE FROM esl_audit_log" in second_sql
        assert "timestamp" in second_sql
        assert second_params == (90,)

    @pytest.mark.asyncio
    async def test_prune_uses_configured_retention_days(self):
        """Patch settings.RETENTION_DAYS=30 — both DELETEs use 30."""
        sched = make_scheduler()
        ctx, cur = _build_db_mock(tool_rowcount=0, audit_rowcount=0)

        from config import settings

        with patch(
            "services.scheduler.get_db_connection", return_value=ctx
        ), patch.object(settings, "RETENTION_DAYS", 30):
            await sched._prune_old_telemetry()

        assert cur.execute.call_count == 2
        for call in cur.execute.call_args_list:
            _, params = call.args
            assert params == (30,)

    @pytest.mark.asyncio
    async def test_prune_swallows_db_errors(self):
        """Errors in the DB layer must be logged, not raised — the scheduler
        thread should keep running."""
        sched = make_scheduler()

        with patch(
            "services.scheduler.get_db_connection",
            side_effect=RuntimeError("db down"),
        ):
            # Must not raise
            await sched._prune_old_telemetry()
