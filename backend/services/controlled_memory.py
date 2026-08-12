"""User-owned, explicit long-term memories."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Json

from utils.db import get_db_connection


class ControlledMemoryService:
    def list(
        self, user_id: str, *, active_only: bool = False, limit: int = 100
    ) -> list[dict[str, Any]]:
        where_active = " AND active = TRUE" if active_only else ""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, content, kind, active, source_turn_id, metadata,
                           created_at, updated_at
                    FROM user_memories
                    WHERE user_id = %s{where_active}
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                return list(cur.fetchall())

    def create(
        self,
        user_id: str,
        *,
        content: str,
        kind: str,
        source_turn_id: str | None = None,
    ) -> dict[str, Any]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_memories (user_id, content, kind, source_turn_id, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, content, kind, active, source_turn_id, metadata,
                              created_at, updated_at
                    """,
                    (
                        user_id,
                        content.strip(),
                        kind,
                        source_turn_id,
                        Json({"created_by": "user"}),
                    ),
                )
                return cur.fetchone()

    def update(
        self,
        user_id: str,
        memory_id: str,
        *,
        content: str | None,
        kind: str | None,
        active: bool | None,
    ) -> dict[str, Any] | None:
        assignments: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("content", content.strip() if content else content),
            ("kind", kind),
            ("active", active),
        ):
            if value is not None:
                assignments.append(f"{column} = %s")
                values.append(value)
        if not assignments:
            return None
        assignments.append("updated_at = NOW()")
        values.extend((memory_id, user_id))
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE user_memories SET {', '.join(assignments)}
                    WHERE id = %s AND user_id = %s
                    RETURNING id, content, kind, active, source_turn_id, metadata,
                              created_at, updated_at
                    """,
                    values,
                )
                return cur.fetchone()

    def forget(self, user_id: str, memory_id: str) -> bool:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM user_memories WHERE id = %s AND user_id = %s",
                    (memory_id, user_id),
                )
                return cur.rowcount > 0
