"""DocumentAgent — semantic search over user-uploaded documents."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Document Analyst. You answer questions by searching the user's uploaded documents "
    "and files. Always quote the source document name when referencing content. "
    "If the answer is not found in documents, say so — do not guess."
)


def build_document_tools(user_id: str, context_manager: Any) -> list[BaseTool]:
    from services.langchain_tools import MemoryQueryTool

    @tool
    async def search_documents(query: str, limit: int = 5) -> str:
        """Semantically search the user's uploaded documents for relevant content."""
        try:
            results = await context_manager.query_semantic_memory(
                user_id=user_id,
                query=query,
                limit=limit,
            )
        except Exception as e:
            return f"Document search failed: {e}"

        if not results:
            return "No relevant document content found."

        lines = []
        for r in results:
            source = getattr(r, "source", "unknown")
            content = getattr(r, "content", "")[:300]
            lines.append(f"[{source}]: {content}")
        return "\n\n".join(lines)

    tools: list[BaseTool] = [search_documents]
    tools.append(MemoryQueryTool(context_manager=context_manager, user_id=user_id))
    return tools


def build_agent(llm: Any, checkpointer: Any, user_id: str = "", context_manager: Any = None):
    """Return a compiled DocumentAgent graph."""
    tools = build_document_tools(user_id=user_id, context_manager=context_manager) if context_manager else []
    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
