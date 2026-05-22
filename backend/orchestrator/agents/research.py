"""ResearchAgent — web search + semantic memory retrieval."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Research Specialist. Your job is to gather information using web search "
    "and the user's past conversation memory. Always cite your sources. "
    "Return a structured response with Key Findings, Sources, and Next Steps. "
    "Never fabricate citations."
)


def build_research_tools(user_id: str, context_manager: Any) -> list[BaseTool]:
    from services.langchain_tools import MemoryQueryTool, WebSearchTool
    tools: list[BaseTool] = []

    if getattr(settings, "TAVILY_API_KEY", None):
        try:
            from tavily import TavilyClient
            tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
            tools.append(
                WebSearchTool(
                    tavily_client=tavily_client,
                    relevance_engine=None,
                    user_id=user_id,
                )
            )
        except Exception:
            pass

    tools.append(MemoryQueryTool(context_manager=context_manager, user_id=user_id))

    return tools


def build_agent(llm: Any, checkpointer: Any, user_id: str = "", context_manager: Any = None):
    """Return a compiled ResearchAgent graph."""
    tools = build_research_tools(user_id=user_id, context_manager=context_manager) if context_manager else []
    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
