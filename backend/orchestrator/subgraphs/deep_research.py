"""DeepResearch subgraph — parallel web search + memory retrieval + synthesis."""

import asyncio
import logging
from orchestrator.state import AgentState
from config import settings

logger = logging.getLogger(__name__)


async def deep_research_node(state: AgentState) -> dict:
    """
    For research_deep intent: run web search + semantic memory in parallel,
    synthesize into a structured response, set proposed_content.
    """
    query = state["message"]
    user_id = state["user_id"]

    async def _web_search():
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults

            if not getattr(settings, "TAVILY_API_KEY", None):
                return []
            tool = TavilySearchResults(max_results=5, api_key=settings.TAVILY_API_KEY)
            return await tool.ainvoke({"query": query})
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
            return []

    async def _memory_search():
        try:
            from orchestrator.nodes.context import get_context_manager

            cm = get_context_manager()
            history = await cm.get_conversation_history(user_id, limit=10)
            return history or []
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")
            return []

    web_results, memory_results = await asyncio.gather(
        _web_search(), _memory_search(), return_exceptions=True
    )
    # Normalize gather exceptions to empty lists
    if isinstance(web_results, Exception):
        web_results = []
    if isinstance(memory_results, Exception):
        memory_results = []

    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import HumanMessage

        llm = ChatGroq(
            model=state.get("model", "llama-3.3-70b-versatile"),
            api_key=settings.GROQ_API_KEY,
        )
        synthesis_prompt = (
            f"Research query: {query}\n\n"
            f"Web search results: {web_results}\n\n"
            f"Relevant past context: {memory_results}\n\n"
            "Provide a comprehensive, well-structured research response with:\n"
            "- **Key findings** (numbered list)\n"
            "- **Sources referenced**\n"
            "- **Recommended next steps**\n\n"
            "Use markdown formatting."
        )
        response = await llm.ainvoke([HumanMessage(content=synthesis_prompt)])
        proposed = response.content
    except Exception as e:
        logger.error(f"Deep research synthesis failed: {e}")
        proposed = f"Research on '{query}' could not be completed. Error: {e}"

    return {"proposed_content": proposed, "tool_calls": [], "tool_results": []}
