"""GoalsAgent — reads user values and goals from M1 (PostgreSQL)."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Goals and Values Coach. You help users reflect on their goals, "
    "understand their stated values, and make decisions aligned with what they care about. "
    "Always reference the user's actual goals — never invent or assume goals they haven't set. "
    "Suggest actions that respect the user's boundaries."
)


def build_goals_tools(user_id: str, context_manager: Any) -> list[BaseTool]:
    from services.langchain_tools import MemoryQueryTool

    @tool
    async def get_user_goals(limit: int = 10) -> str:
        """Retrieve the user's active goals from the database."""
        try:
            from utils.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT title, description, status, priority
                        FROM goals
                        WHERE user_id = %s AND status != 'archived'
                        ORDER BY priority DESC, created_at DESC
                        LIMIT %s
                        """,
                        (user_id, limit),
                    )
                    rows = cur.fetchall()
        except Exception as e:
            return f"Could not retrieve goals: {e}"

        if not rows:
            return "No active goals found."

        lines = [f"- [{row[2]}] {row[0]}" + (f": {row[1][:100]}" if row[1] else "") for row in rows]
        return "\n".join(lines)

    @tool
    async def get_user_values() -> str:
        """Retrieve the user's stated values and boundaries."""
        try:
            from utils.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT value_name, description, boundary_type FROM user_values WHERE user_id = %s",
                        (user_id,),
                    )
                    rows = cur.fetchall()
        except Exception as e:
            return f"Could not retrieve values: {e}"

        if not rows:
            return "No values configured."

        return "\n".join(f"- {row[0]} ({row[2]}): {row[1] or ''}" for row in rows)

    tools: list[BaseTool] = [get_user_goals, get_user_values]
    tools.append(MemoryQueryTool(context_manager=context_manager, user_id=user_id))
    return tools


def build_agent(llm: Any, checkpointer: Any, user_id: str = "", context_manager: Any = None):
    """Return a compiled GoalsAgent graph."""
    tools = build_goals_tools(user_id=user_id, context_manager=context_manager) if context_manager else []
    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
