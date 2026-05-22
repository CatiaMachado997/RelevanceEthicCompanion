"""CalendarAgent — reads Google Calendar events for the user."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Calendar Assistant. You help users understand their schedule, "
    "find free time, and summarise upcoming events. "
    "Only read events — never create or modify calendar entries unless explicitly asked. "
    "Always present times in the user's local timezone."
)


def build_calendar_tools(user_id: str, context_manager: Any) -> list[BaseTool]:
    from services.langchain_tools import MemoryQueryTool

    @tool
    async def query_calendar(query: str) -> str:
        """Retrieve Google Calendar events relevant to the query."""
        try:
            from utils.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT title, start_time, end_time, description
                        FROM source_items
                        WHERE user_id = %s
                          AND source_type = 'google_calendar'
                          AND (title ILIKE %s OR description ILIKE %s)
                        ORDER BY start_time
                        LIMIT 10
                        """,
                        (user_id, f"%{query}%", f"%{query}%"),
                    )
                    rows = cur.fetchall()
        except Exception as e:
            return f"Calendar lookup failed: {e}"

        if not rows:
            return "No calendar events found matching your query."

        lines = []
        for title, start, end, desc in rows:
            lines.append(f"- {title}: {start} → {end}" + (f" ({desc[:80]})" if desc else ""))
        return "\n".join(lines)

    tools: list[BaseTool] = [query_calendar]
    tools.append(MemoryQueryTool(context_manager=context_manager, user_id=user_id))
    return tools


def build_agent(llm: Any, checkpointer: Any, user_id: str = "", context_manager: Any = None):
    """Return a compiled CalendarAgent graph."""
    tools = build_calendar_tools(user_id=user_id, context_manager=context_manager) if context_manager else []
    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
