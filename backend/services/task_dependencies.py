"""Task dependencies service — Sprint D Task 2.

Manages the many-to-many dependency edges between tasks (table:
``task_dependencies`` from migration 011). Cycle prevention is enforced
in this service layer via a recursive CTE reachability check.

Edge semantics:
    (task_id, depends_on_task_id) means "task_id depends on
    depends_on_task_id" — i.e. depends_on_task_id is a *blocker* of task_id.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from psycopg.errors import IntegrityError, UniqueViolation

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


# ── Cycle-check CTE ─────────────────────────────────────────────────────────
# Starting from `depends_on_task_id` (B), walk task_id -> depends_on_task_id
# edges and check whether `task_id` (A) is reachable. If so, adding A->B
# would close a cycle.
_CYCLE_CHECK_SQL = """
WITH RECURSIVE reachable(task_id) AS (
    SELECT depends_on_task_id
    FROM task_dependencies
    WHERE task_id = %s
    UNION
    SELECT td.depends_on_task_id
    FROM task_dependencies td
    JOIN reachable r ON td.task_id = r.task_id
)
SELECT 1 FROM reachable WHERE task_id = %s LIMIT 1;
"""

_INSERT_SQL = """
INSERT INTO task_dependencies (task_id, depends_on_task_id)
VALUES (%s, %s);
"""

_DELETE_SQL = """
DELETE FROM task_dependencies
WHERE task_id = %s AND depends_on_task_id = %s;
"""

# Transitive blockers of a task: every task this task depends on (direct +
# indirect). Returns shallowest depth per blocker.
_BLOCKERS_SQL = """
WITH RECURSIVE blockers(task_id, depth) AS (
    SELECT depends_on_task_id, 1
    FROM task_dependencies
    WHERE task_id = %s
    UNION
    SELECT td.depends_on_task_id, b.depth + 1
    FROM task_dependencies td
    JOIN blockers b ON td.task_id = b.task_id
)
SELECT t.id AS task_id, t.title, t.status, MIN(b.depth) AS depth
FROM blockers b
JOIN tasks t ON t.id = b.task_id
GROUP BY t.id, t.title, t.status
ORDER BY depth, t.title;
"""

# Transitive "blocked-by": every task that depends on this one.
_BLOCKED_BY_SQL = """
WITH RECURSIVE dependents(task_id, depth) AS (
    SELECT task_id, 1
    FROM task_dependencies
    WHERE depends_on_task_id = %s
    UNION
    SELECT td.task_id, d.depth + 1
    FROM task_dependencies td
    JOIN dependents d ON td.depends_on_task_id = d.task_id
)
SELECT t.id AS task_id, t.title, t.status, MIN(d.depth) AS depth
FROM dependents d
JOIN tasks t ON t.id = d.task_id
GROUP BY t.id, t.title, t.status
ORDER BY depth, t.title;
"""


class TaskDependenciesService:
    """Service for managing task dependency edges with cycle prevention."""

    def add_dependency(self, task_id: str, depends_on_task_id: str) -> None:
        """Insert (task_id depends on depends_on_task_id).

        Raises:
            ValueError: on self-dependency, cycle, or duplicate edge.
        """
        if task_id == depends_on_task_id:
            raise ValueError("A task cannot depend on itself")

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Cycle check: would adding A->B make A reachable from B?
                cur.execute(
                    _CYCLE_CHECK_SQL, (depends_on_task_id, task_id)
                )
                if cur.fetchone() is not None:
                    raise ValueError(
                        f"Adding dependency {task_id} -> {depends_on_task_id} "
                        "would create a cycle"
                    )

                try:
                    cur.execute(_INSERT_SQL, (task_id, depends_on_task_id))
                except (UniqueViolation, IntegrityError) as exc:
                    raise ValueError(
                        f"Dependency {task_id} -> {depends_on_task_id} already exists"
                    ) from exc

            conn.commit()
        logger.info(
            "Added task dependency %s -> %s", task_id, depends_on_task_id
        )

    def remove_dependency(self, task_id: str, depends_on_task_id: str) -> bool:
        """Delete the edge. Returns True if a row was removed."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_DELETE_SQL, (task_id, depends_on_task_id))
                removed = cur.rowcount > 0
            conn.commit()
        logger.info(
            "Removed task dependency %s -> %s (existed=%s)",
            task_id,
            depends_on_task_id,
            removed,
        )
        return removed

    def get_blockers(self, task_id: str) -> List[Dict[str, Any]]:
        """Direct + transitive blockers of `task_id`.

        Returns list of dicts {task_id, title, status, depth}.
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_BLOCKERS_SQL, (task_id,))
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_blocked_by(self, task_id: str) -> List[Dict[str, Any]]:
        """Direct + transitive tasks that depend on `task_id`.

        Returns list of dicts {task_id, title, status, depth}.
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_BLOCKED_BY_SQL, (task_id,))
                rows = cur.fetchall()
        return [dict(r) for r in rows]
