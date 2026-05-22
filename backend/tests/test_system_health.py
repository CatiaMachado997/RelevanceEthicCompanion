"""Sprint E Task 2: SystemHealthService tests.

All DB-backed tests use a mocked cursor — no live Postgres required.
The scheduler test mocks the module-level singleton accessor.
"""

from unittest.mock import MagicMock, patch


USER_ID = "11111111-1111-1111-1111-111111111111"


def _mock_db(cur: MagicMock):
    """Build a get_db_connection() context manager that yields a conn whose
    cursor() context manager yields ``cur``."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    db_ctx = MagicMock()
    db_ctx.__enter__.return_value = conn
    db_ctx.__exit__.return_value = False
    return db_ctx


@patch("services.system_health.get_db_connection")
def test_get_tool_health_queries_view(mock_get_db):
    from services.system_health import SystemHealthService

    cur = MagicMock()
    cur.fetchall.return_value = [
        {
            "tool_name": "search_documents",
            "source": "agent",
            "calls_24h": 42,
            "success_rate": 95,
            "p50_latency_ms": 120,
            "p95_latency_ms": 480,
        },
        {
            "tool_name": "weekly_digest",
            "source": "scheduled",
            "calls_24h": 3,
            "success_rate": 100,
            "p50_latency_ms": 800,
            "p95_latency_ms": 1200,
        },
    ]
    mock_get_db.return_value = _mock_db(cur)

    svc = SystemHealthService()
    result = svc.get_tool_health(USER_ID)

    # SQL hits the view with the user id parameter
    sql = cur.execute.call_args.args[0]
    assert "v_tool_call_health" in sql
    assert cur.execute.call_args.args[1] == (USER_ID,)

    # Rows roundtrip as dicts
    assert len(result) == 2
    assert result[0]["tool_name"] == "search_documents"
    assert result[0]["p95_latency_ms"] == 480
    assert result[1]["source"] == "scheduled"


@patch("services.system_health.get_db_connection")
def test_get_esl_summary_rollup_shape(mock_get_db):
    from services.system_health import SystemHealthService

    cur = MagicMock()
    cur.fetchall.return_value = [
        {"decision_status": "APPROVED", "count_24h": 12, "count_7d": 80},
        {"decision_status": "MODIFIED", "count_24h": 2, "count_7d": 9},
        {"decision_status": "VETOED", "count_24h": 1, "count_7d": 4},
    ]
    mock_get_db.return_value = _mock_db(cur)

    svc = SystemHealthService()
    result = svc.get_esl_summary(USER_ID)

    sql = cur.execute.call_args.args[0]
    assert "v_esl_decision_summary" in sql
    assert cur.execute.call_args.args[1] == (USER_ID,)

    assert result == {
        "APPROVED": {"count_24h": 12, "count_7d": 80},
        "MODIFIED": {"count_24h": 2, "count_7d": 9},
        "VETOED": {"count_24h": 1, "count_7d": 4},
    }


@patch("services.scheduler.get_scheduler_instance")
def test_get_scheduler_status_returns_jobs(mock_get_inst):
    from datetime import datetime, timezone

    from services.system_health import SystemHealthService

    next_run = datetime(2026, 4, 27, 8, 0, tzinfo=timezone.utc)

    job1 = MagicMock()
    job1.id = "weekly_digest"
    job1.next_run_time = next_run
    job1.trigger = "cron[day_of_week='mon', hour='8']"

    job2 = MagicMock()
    job2.id = "sync_google_calendar"
    job2.next_run_time = None
    job2.trigger = "interval[0:15:00]"

    fake_inst = MagicMock()
    fake_inst._running = True
    fake_inst.scheduler.get_jobs.return_value = [job1, job2]
    mock_get_inst.return_value = fake_inst

    svc = SystemHealthService()
    result = svc.get_scheduler_status()

    assert len(result) == 2
    assert result[0]["job_id"] == "weekly_digest"
    assert result[0]["next_run_time"] == next_run.isoformat()
    assert "cron" in result[0]["trigger"]
    assert result[1]["job_id"] == "sync_google_calendar"
    assert result[1]["next_run_time"] is None


@patch("services.scheduler.get_scheduler_instance")
def test_get_scheduler_status_empty_when_not_running(mock_get_inst):
    """If the scheduler hasn't started (or in tests), return an empty list."""
    from services.system_health import SystemHealthService

    mock_get_inst.return_value = None

    svc = SystemHealthService()
    assert svc.get_scheduler_status() == []
