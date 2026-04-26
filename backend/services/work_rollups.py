"""Work rollups service — Sprint D Task 3.

Aggregates project/goal progress and weekly review data using the
``v_project_rollup`` and ``v_goal_rollup`` views from migration 011, plus
ad-hoc queries against ``tasks`` and ``goal_milestones`` for the weekly
review.

Sync, class-based, mirrors :class:`services.task_dependencies.TaskDependenciesService`.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


_PROJECT_ROLLUP_SQL = """
SELECT project_id, tasks_total, tasks_done, tasks_open,
       at_risk_count, completion_pct
FROM v_project_rollup
WHERE project_id = %s;
"""

_GOAL_ROLLUP_SQL = """
SELECT goal_id, milestones_total, milestones_hit,
       tasks_total, tasks_done, progress_pct
FROM v_goal_rollup
WHERE goal_id = %s;
"""

# Weekly-review queries ------------------------------------------------------
# NOTE: the `tasks` schema has no `completed_at` column. We use `updated_at`
# as a proxy for completion time when status='done'. This is documented on
# get_weekly_review() as well.
_COMPLETED_TASKS_SQL = """
SELECT id, title, updated_at AS completed_at, project_id, goal_id
FROM tasks
WHERE user_id = %s
  AND status = 'done'
  AND updated_at >= %s
  AND updated_at < %s
ORDER BY updated_at;
"""

_COMPLETED_MILESTONES_SQL = """
SELECT id, title, goal_id, completed_at
FROM goal_milestones
WHERE user_id = %s
  AND completed = TRUE
  AND completed_at IS NOT NULL
  AND completed_at >= %s
  AND completed_at < %s
ORDER BY completed_at;
"""

_CARRY_OVER_TASKS_SQL = """
SELECT id, title, due_date, status
FROM tasks
WHERE user_id = %s
  AND due_date IS NOT NULL
  AND due_date < %s
  AND status NOT IN ('done', 'cancelled')
ORDER BY due_date;
"""

_UPCOMING_TASKS_SQL = """
SELECT id, title, due_date, status
FROM tasks
WHERE user_id = %s
  AND due_date IS NOT NULL
  AND due_date >= %s
  AND due_date < %s
  AND status NOT IN ('done', 'cancelled')
ORDER BY due_date;
"""

_UPCOMING_MILESTONES_SQL = """
SELECT id, title, goal_id, target_date
FROM goal_milestones
WHERE user_id = %s
  AND target_date IS NOT NULL
  AND target_date >= %s
  AND target_date < %s
  AND completed = FALSE
ORDER BY target_date;
"""


def _most_recent_monday_utc() -> date:
    """Return the most recent Monday (00:00 UTC) on or before today."""
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday())  # Monday is 0


class WorkRollupsService:
    """Service for project/goal/weekly aggregations."""

    def get_project_rollup(self, project_id: str) -> Dict[str, Any]:
        """SELECT from ``v_project_rollup``; returns ``{}`` if not found.

        Shape: ``{project_id, tasks_total, tasks_done, tasks_open,
        at_risk_count, completion_pct}``.
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_PROJECT_ROLLUP_SQL, (project_id,))
                row = cur.fetchone()
        if row is None:
            return {}
        return dict(row)

    def get_goal_rollup(self, goal_id: str) -> Dict[str, Any]:
        """SELECT from ``v_goal_rollup``; returns ``{}`` if not found.

        Shape: ``{goal_id, milestones_total, milestones_hit, tasks_total,
        tasks_done, progress_pct}``.
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_GOAL_ROLLUP_SQL, (goal_id,))
                row = cur.fetchone()
        if row is None:
            return {}
        return dict(row)

    def get_weekly_review(
        self, user_id: str, week_start: Optional[date] = None
    ) -> Dict[str, Any]:
        """Aggregate the user's last week of work.

        ``week_start`` defaults to the most recent Monday 00:00 UTC.

        Note: the ``tasks`` table has no ``completed_at`` column, so this
        method uses ``updated_at`` as a proxy for the completion time of
        tasks whose status is ``'done'``.

        Returns::

            {
              "period": {"start": ISO, "end": ISO},   # end = start + 7 days
              "completed_tasks":      [{id, title, completed_at, project_id, goal_id}],
              "completed_milestones": [{id, title, goal_id, completed_at}],
              "carry_over_tasks":     [{id, title, due_date, status}],
              "upcoming_tasks":       [{id, title, due_date, status}],
              "upcoming_milestones":  [{id, title, goal_id, target_date}],
            }
        """
        if week_start is None:
            week_start = _most_recent_monday_utc()
        period_end = week_start + timedelta(days=7)
        upcoming_end = period_end + timedelta(days=7)

        # Datetimes for TIMESTAMPTZ comparisons.
        start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(period_end, datetime.min.time(), tzinfo=timezone.utc)
        upcoming_end_dt = datetime.combine(
            upcoming_end, datetime.min.time(), tzinfo=timezone.utc
        )

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_COMPLETED_TASKS_SQL, (user_id, start_dt, end_dt))
                completed_tasks = [dict(r) for r in cur.fetchall()]

                cur.execute(
                    _COMPLETED_MILESTONES_SQL, (user_id, start_dt, end_dt)
                )
                completed_milestones = [dict(r) for r in cur.fetchall()]

                cur.execute(_CARRY_OVER_TASKS_SQL, (user_id, end_dt))
                carry_over_tasks = [dict(r) for r in cur.fetchall()]

                cur.execute(
                    _UPCOMING_TASKS_SQL, (user_id, end_dt, upcoming_end_dt)
                )
                upcoming_tasks = [dict(r) for r in cur.fetchall()]

                cur.execute(
                    _UPCOMING_MILESTONES_SQL,
                    (user_id, period_end, upcoming_end),
                )
                upcoming_milestones = [dict(r) for r in cur.fetchall()]

        return {
            "period": {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
            },
            "completed_tasks": completed_tasks,
            "completed_milestones": completed_milestones,
            "carry_over_tasks": carry_over_tasks,
            "upcoming_tasks": upcoming_tasks,
            "upcoming_milestones": upcoming_milestones,
        }
