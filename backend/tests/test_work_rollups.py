"""Sprint D Task 3: WorkRollupsService tests.

All tests use a mocked DB cursor — no live Postgres required.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


USER_ID = "11111111-1111-1111-1111-111111111111"
PROJECT_ID = "22222222-2222-2222-2222-222222222222"
GOAL_ID = "33333333-3333-3333-3333-333333333333"


def _mock_db(cur: MagicMock):
    """Build a get_db_connection() context manager that yields a conn whose
    cursor() context manager yields `cur`."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    db_ctx = MagicMock()
    db_ctx.__enter__.return_value = conn
    db_ctx.__exit__.return_value = False
    return db_ctx, conn


@patch("services.work_rollups.get_db_connection")
def test_project_rollup_with_zero_tasks(mock_get_db):
    from services.work_rollups import WorkRollupsService

    cur = MagicMock()
    cur.fetchone.return_value = {
        "project_id": PROJECT_ID,
        "tasks_total": 0,
        "tasks_done": 0,
        "tasks_open": 0,
        "at_risk_count": 0,
        "completion_pct": 0,
    }
    db_ctx, _ = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = WorkRollupsService()
    result = svc.get_project_rollup(PROJECT_ID)

    assert result["project_id"] == PROJECT_ID
    assert result["tasks_total"] == 0
    assert result["completion_pct"] == 0

    sql = cur.execute.call_args.args[0]
    assert "v_project_rollup" in sql
    assert cur.execute.call_args.args[1] == (PROJECT_ID,)


@patch("services.work_rollups.get_db_connection")
def test_project_rollup_all_done(mock_get_db):
    from services.work_rollups import WorkRollupsService

    cur = MagicMock()
    cur.fetchone.return_value = {
        "project_id": PROJECT_ID,
        "tasks_total": 4,
        "tasks_done": 4,
        "tasks_open": 0,
        "at_risk_count": 0,
        "completion_pct": 100,
    }
    db_ctx, _ = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = WorkRollupsService()
    result = svc.get_project_rollup(PROJECT_ID)

    assert result["tasks_total"] == 4
    assert result["tasks_done"] == 4
    assert result["completion_pct"] == 100


@patch("services.work_rollups.get_db_connection")
def test_goal_rollup_milestones_first(mock_get_db):
    from services.work_rollups import WorkRollupsService

    cur = MagicMock()
    cur.fetchone.return_value = {
        "goal_id": GOAL_ID,
        "milestones_total": 5,
        "milestones_hit": 2,
        "tasks_total": 10,
        "tasks_done": 7,
        "progress_pct": 40,  # view picks milestone-based math: 2/5 = 40
    }
    db_ctx, _ = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = WorkRollupsService()
    result = svc.get_goal_rollup(GOAL_ID)

    assert result["goal_id"] == GOAL_ID
    assert result["milestones_total"] == 5
    assert result["milestones_hit"] == 2
    # The view does the math; the service just returns it.
    assert result["progress_pct"] == 40

    sql = cur.execute.call_args.args[0]
    assert "v_goal_rollup" in sql
    assert cur.execute.call_args.args[1] == (GOAL_ID,)


@patch("services.work_rollups.get_db_connection")
def test_weekly_review_default_week_start(mock_get_db):
    from services.work_rollups import WorkRollupsService, _most_recent_monday_utc

    cur = MagicMock()
    cur.fetchall.return_value = []
    db_ctx, _ = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = WorkRollupsService()
    result = svc.get_weekly_review(USER_ID, week_start=None)

    expected_monday = _most_recent_monday_utc()
    expected_start_dt = datetime.combine(
        expected_monday, datetime.min.time(), tzinfo=timezone.utc
    )
    expected_end_dt = expected_start_dt + timedelta(days=7)

    # Five SELECTs are run.
    assert cur.execute.call_count == 5

    # First call (completed tasks) should use start_dt and end_dt.
    first_params = cur.execute.call_args_list[0].args[1]
    assert first_params == (USER_ID, expected_start_dt, expected_end_dt)

    # Period in result reflects the most-recent-Monday-UTC default.
    assert result["period"]["start"] == expected_start_dt.isoformat()
    assert result["period"]["end"] == expected_end_dt.isoformat()


@patch("services.work_rollups.get_db_connection")
def test_weekly_review_returns_zero_shape_for_empty_user(mock_get_db):
    from services.work_rollups import WorkRollupsService

    cur = MagicMock()
    cur.fetchall.return_value = []
    db_ctx, _ = _mock_db(cur)
    mock_get_db.return_value = db_ctx

    svc = WorkRollupsService()
    fixed_monday = date(2026, 4, 20)  # known Monday
    result = svc.get_weekly_review(USER_ID, week_start=fixed_monday)

    assert result["completed_tasks"] == []
    assert result["completed_milestones"] == []
    assert result["carry_over_tasks"] == []
    assert result["upcoming_tasks"] == []
    assert result["upcoming_milestones"] == []
    assert "period" in result
    assert result["period"]["start"].startswith("2026-04-20")
    assert result["period"]["end"].startswith("2026-04-27")
