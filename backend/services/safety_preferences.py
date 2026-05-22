"""Sprint J Task 7: layered safety preferences.

Three layers, in priority order:
  1. users.safe_mode_enabled — master toggle.
  2. user_category_preferences — by tool category.
  3. user_tool_preferences — by tool name.

Resolution: pause if ANY layer says so. The "Trust this tool from now
on" action deletes only the per-tool row; higher layers stick.

Like other telemetry services in this codebase (services/tool_telemetry
.py, services/planner_runs.py), all DB failures are logged at WARNING
and swallowed — preference reads default to "no confirmation needed"
on error so a DB outage doesn't paralyze the agent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Set

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


_VALID_CATEGORIES = frozenset(
    {"read-personal", "read-external", "write-personal", "write-external"}
)


@dataclass
class SafetyPreferences:
    """Frozen snapshot of one user's safety preferences."""

    safe_mode_enabled: bool
    categories: Set[str] = field(default_factory=set)
    tools: Set[str] = field(default_factory=set)

    def should_confirm(self, *, tool_name: str, category: str) -> bool:
        """Return True if any layer requires confirmation for this action."""
        if self.safe_mode_enabled:
            return True
        if category in self.categories:
            return True
        if tool_name in self.tools:
            return True
        return False

    def explain_reason(self, *, tool_name: str, category: str) -> str:
        """Human-readable explanation of which layer caught the action.

        Priority: master > category > per-tool. Returned string is shown
        to the user under the paused action chip.
        """
        if self.safe_mode_enabled:
            return "Safe mode is on — every action waits for your approval."
        if category in self.categories:
            return f"Category '{category}' is set to ask before running."
        if tool_name in self.tools:
            return f"Tool '{tool_name}' is set to ask before running."
        return ""


class SafetyPreferencesService:
    """Read + write the three preference layers."""

    def load_for_user(self, user_id: str) -> SafetyPreferences:
        """Return a SafetyPreferences for `user_id`. On any DB failure,
        return a permissive default (safe_mode off, no categories, no
        tools) so the agent doesn't deadlock."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT safe_mode_enabled FROM users WHERE id = %s",
                        (user_id,),
                    )
                    row = cur.fetchone() or {}
                    safe_mode = bool(row.get("safe_mode_enabled"))

                    cur.execute(
                        """SELECT category
                             FROM user_category_preferences
                            WHERE user_id = %s
                              AND requires_confirmation = TRUE""",
                        (user_id,),
                    )
                    categories = {r["category"] for r in (cur.fetchall() or [])}

                    cur.execute(
                        """SELECT tool_name
                             FROM user_tool_preferences
                            WHERE user_id = %s
                              AND requires_confirmation = TRUE""",
                        (user_id,),
                    )
                    tools = {r["tool_name"] for r in (cur.fetchall() or [])}
            return SafetyPreferences(
                safe_mode_enabled=safe_mode, categories=categories, tools=tools
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "safety_preferences: load failed for user %s: %s", user_id, exc
            )
            return SafetyPreferences(safe_mode_enabled=False)

    def set_safe_mode(self, user_id: str, *, enabled: bool) -> None:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET safe_mode_enabled = %s WHERE id = %s",
                        (enabled, user_id),
                    )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "safety_preferences: set_safe_mode failed for %s: %s", user_id, exc
            )

    def set_category(
        self,
        user_id: str,
        *,
        category: str,
        requires_confirmation: bool,
    ) -> None:
        if category not in _VALID_CATEGORIES:
            logger.warning(
                "safety_preferences: refused unknown category %r", category
            )
            return
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if requires_confirmation:
                        cur.execute(
                            """INSERT INTO user_category_preferences
                                   (user_id, category, requires_confirmation)
                               VALUES (%s, %s, TRUE)
                               ON CONFLICT (user_id, category)
                                  DO UPDATE SET requires_confirmation = TRUE""",
                            (user_id, category),
                        )
                    else:
                        cur.execute(
                            """DELETE FROM user_category_preferences
                                WHERE user_id = %s AND category = %s""",
                            (user_id, category),
                        )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "safety_preferences: set_category failed for %s/%s: %s",
                user_id,
                category,
                exc,
            )

    def set_tool(
        self,
        user_id: str,
        *,
        tool_name: str,
        requires_confirmation: bool,
    ) -> None:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if requires_confirmation:
                        cur.execute(
                            """INSERT INTO user_tool_preferences
                                   (user_id, tool_name, requires_confirmation)
                               VALUES (%s, %s, TRUE)
                               ON CONFLICT (user_id, tool_name)
                                  DO UPDATE SET requires_confirmation = TRUE""",
                            (user_id, tool_name),
                        )
                    else:
                        cur.execute(
                            """DELETE FROM user_tool_preferences
                                WHERE user_id = %s AND tool_name = %s""",
                            (user_id, tool_name),
                        )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "safety_preferences: set_tool failed for %s/%s: %s",
                user_id,
                tool_name,
                exc,
            )

    def delete_tool(self, user_id: str, *, tool_name: str) -> None:
        """Idempotent removal of a per-tool row. Used by the 'Trust this
        tool from now on' action; deleting a row that doesn't exist is
        fine — no rows affected, no error."""
        self.set_tool(user_id, tool_name=tool_name, requires_confirmation=False)
