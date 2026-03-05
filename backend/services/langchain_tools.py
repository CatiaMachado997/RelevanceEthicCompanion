"""
LangChain Tool Definitions for V2 Orchestrator

Converts internal tools to LangChain-compatible format for agent use.
"""

from typing import Optional, Type, Any, Dict
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


# ==================== Memory Query Tool ====================

class MemoryQueryInput(BaseModel):
    """Input for the memory query tool"""
    query: str = Field(description="Search query to find relevant conversation history and context")
    limit: int = Field(default=5, description="Maximum number of memory entries to retrieve")


class MemoryQueryTool(BaseTool):
    """Tool for querying semantic memory (Weaviate M2)"""

    name: str = "query_memory"
    description: str = (
        "Search conversation history and semantic memory for relevant information. "
        "Use this when you need to recall past conversations, user preferences, "
        "or contextual information from previous interactions."
    )
    args_schema: Type[BaseModel] = MemoryQueryInput

    # Custom attributes for dependency injection
    context_manager: Any = None
    user_id: str = ""

    def __init__(self, context_manager, user_id: str):
        super().__init__()
        self.context_manager = context_manager
        self.user_id = user_id

    async def _arun(self, query: str, limit: int = 5) -> str:
        """Async implementation (LangChain requirement)"""
        try:
            results = await self.context_manager.query_semantic_memory(
                user_id=self.user_id,
                query=query,
                limit=limit
            )

            if not results:
                return "No relevant memories found."

            # Format results as text
            memory_text = f"Found {len(results)} relevant memories:\n\n"
            for i, memory in enumerate(results, 1):
                memory_text += f"{i}. {memory.content[:200]}"
                if len(memory.content) > 200:
                    memory_text += "..."
                memory_text += f" (source: {memory.source})\n"

            return memory_text

        except Exception as e:
            logger.error(f"Memory query failed: {e}")
            return f"Error querying memory: {str(e)}"

    def _run(self, query: str, limit: int = 5) -> str:
        """Sync implementation (not used but required by LangChain)"""
        raise NotImplementedError("Use async version (_arun)")


# ==================== Calendar Query Tool ====================

class CalendarQueryInput(BaseModel):
    """Input for the calendar query tool"""
    time_frame: str = Field(
        default="today",
        description="Time frame for calendar events: 'today', 'tomorrow', 'this week', 'next week', or number of hours (e.g., '24')"
    )


class CalendarQueryTool(BaseTool):
    """Tool for querying upcoming calendar events"""

    name: str = "query_calendar"
    description: str = (
        "Get upcoming calendar events for the user. "
        "Use this to check what's on the user's schedule, find meeting times, "
        "or provide context about upcoming commitments."
    )
    args_schema: Type[BaseModel] = CalendarQueryInput

    # Custom attributes
    context_manager: Any = None
    user_id: str = ""

    def __init__(self, context_manager, user_id: str):
        super().__init__()
        self.context_manager = context_manager
        self.user_id = user_id

    async def _arun(self, time_frame: str = "today") -> str:
        """Async implementation"""
        try:
            # Map time_frame to hours
            time_map = {
                "today": 24,
                "tomorrow": 48,
                "this week": 168,
                "next week": 336
            }

            hours_ahead = time_map.get(time_frame.lower(), 24)

            # Try to parse as number of hours
            try:
                hours_ahead = int(time_frame)
            except (ValueError, TypeError):
                pass

            events = await self.context_manager.get_upcoming_events(
                user_id=self.user_id,
                hours_ahead=hours_ahead
            )

            if not events:
                return f"No events scheduled for {time_frame}."

            # Format events as text
            event_text = f"Found {len(events)} events for {time_frame}:\n\n"
            for i, event in enumerate(events, 1):
                event_text += f"{i}. {event.title}"
                if event.start_time:
                    event_text += f" at {event.start_time.strftime('%I:%M %p on %b %d')}"
                if event.location:
                    event_text += f" ({event.location})"
                event_text += "\n"
                if event.description:
                    desc_preview = event.description[:100]
                    if len(event.description) > 100:
                        desc_preview += "..."
                    event_text += f"   Description: {desc_preview}\n"

            return event_text

        except Exception as e:
            logger.error(f"Calendar query failed: {e}")
            return f"Error querying calendar: {str(e)}"

    def _run(self, time_frame: str = "today") -> str:
        """Sync implementation (not used)"""
        raise NotImplementedError("Use async version (_arun)")


# ==================== Web Search Tool ====================

class WebSearchInput(BaseModel):
    """Input for the web search tool"""
    query: str = Field(description="Search query to find information on the web")
    max_results: int = Field(default=5, description="Maximum number of search results to return")


class WebSearchTool(BaseTool):
    """Tool for searching the web using Tavily"""

    name: str = "web_search"
    description: str = (
        "Search the web for current information, news, or resources. "
        "Use this when the user asks about current events, recent information, "
        "or topics not in conversation history. "
        "Results will be ranked by relevance to user's goals and values."
    )
    args_schema: Type[BaseModel] = WebSearchInput

    # Custom attributes
    tavily_client: Any = None
    relevance_engine: Any = None
    user_id: str = ""

    def __init__(self, tavily_client, relevance_engine, user_id: str):
        super().__init__()
        self.tavily_client = tavily_client
        self.relevance_engine = relevance_engine
        self.user_id = user_id

    async def _arun(self, query: str, max_results: int = 5) -> str:
        """Async implementation with relevance scoring"""
        try:
            # Perform web search using Tavily
            search_results = self.tavily_client.search(
                query=query,
                max_results=max_results * 2  # Get more, then rank
            )

            if not search_results or not search_results.get("results"):
                return f"No search results found for: {query}"

            # Convert search results to CandidateItems for relevance scoring
            from models.relevance import CandidateItem
            from datetime import datetime, UTC

            candidates = []
            for result in search_results["results"]:
                candidates.append(CandidateItem(
                    id=result.get("url", ""),
                    type="search_result",
                    content=result.get("content", ""),
                    title=result.get("title", ""),
                    source=result.get("url", ""),
                    timestamp=datetime.now(UTC),
                    metadata={
                        "score": result.get("score", 0),
                        "published_date": result.get("published_date", "")
                    }
                ))

            # Score and rank candidates using relevance engine
            scored_items = await self.relevance_engine.score_candidates(
                user_id=self.user_id,
                candidates=candidates,
                query_context=query
            )

            # Take top results after scoring
            top_results = scored_items[:max_results]

            if not top_results:
                return f"Found search results but none were relevant to your goals/values for: {query}"

            # Format results
            results_text = f"Found {len(top_results)} relevant search results for '{query}':\n\n"
            for i, scored in enumerate(top_results, 1):
                results_text += f"{i}. {scored.item.title}\n"
                results_text += f"   URL: {scored.item.source}\n"
                results_text += f"   Relevance: {scored.relevance_score:.0f}/100 - {scored.explanation}\n"
                content_preview = scored.item.content[:150]
                if len(scored.item.content) > 150:
                    content_preview += "..."
                results_text += f"   Summary: {content_preview}\n\n"

            return results_text

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"Error performing web search: {str(e)}"

    def _run(self, query: str, max_results: int = 5) -> str:
        """Sync implementation (not used)"""
        raise NotImplementedError("Use async version (_arun)")


# ==================== User Goals Tool ====================

class UserGoalsInput(BaseModel):
    """Input for the user goals tool"""
    status: str = Field(
        default="active",
        description="Filter goals by status: 'active', 'completed', or 'all'"
    )


class UserGoalsTool(BaseTool):
    """Tool for retrieving user's goals"""

    name: str = "get_user_goals"
    description: str = (
        "Get the user's current goals and priorities. "
        "Use this to understand what the user is working towards "
        "and provide contextually relevant suggestions."
    )
    args_schema: Type[BaseModel] = UserGoalsInput

    # Custom attributes
    context_manager: Any = None
    user_id: str = ""

    def __init__(self, context_manager, user_id: str):
        super().__init__()
        self.context_manager = context_manager
        self.user_id = user_id

    async def _arun(self, status: str = "active") -> str:
        """Async implementation"""
        try:
            goals = await self.context_manager.get_active_goals(self.user_id)

            if not goals:
                return "No active goals found for the user."

            # Filter by status if needed
            if status == "completed":
                goals = [g for g in goals if g.status == "completed"]
            elif status == "active":
                goals = [g for g in goals if g.status != "completed"]

            if not goals:
                return f"No {status} goals found."

            # Format goals as text
            goals_text = f"User's {status} goals ({len(goals)}):\n\n"
            for i, goal in enumerate(goals, 1):
                goals_text += f"{i}. {goal.title}"
                if goal.target_date:
                    goals_text += f" (target: {goal.target_date.strftime('%b %d, %Y')})"
                goals_text += f" [Priority: {goal.priority}]\n"
                if goal.description:
                    desc_preview = goal.description[:100]
                    if len(goal.description) > 100:
                        desc_preview += "..."
                    goals_text += f"   Description: {desc_preview}\n"

            return goals_text

        except Exception as e:
            logger.error(f"Goals query failed: {e}")
            return f"Error retrieving goals: {str(e)}"

    def _run(self, status: str = "active") -> str:
        """Sync implementation (not used)"""
        raise NotImplementedError("Use async version (_arun)")


# ==================== Tool Factory ====================

def create_langchain_tools(
    context_manager,
    user_id: str,
    tavily_client=None,
    relevance_engine=None
) -> list:
    """
    Factory function to create all LangChain tools with dependencies injected.

    Args:
        context_manager: ContextManager instance for M1/M2 access
        user_id: Current user ID
        tavily_client: Optional Tavily client for web search
        relevance_engine: Optional RelevanceScoring engine

    Returns:
        List of initialized LangChain tools
    """
    tools = [
        MemoryQueryTool(context_manager=context_manager, user_id=user_id),
        CalendarQueryTool(context_manager=context_manager, user_id=user_id),
        UserGoalsTool(context_manager=context_manager, user_id=user_id),
    ]

    # Add web search if clients are provided
    if tavily_client and relevance_engine:
        tools.append(WebSearchTool(
            tavily_client=tavily_client,
            relevance_engine=relevance_engine,
            user_id=user_id
        ))

    return tools
