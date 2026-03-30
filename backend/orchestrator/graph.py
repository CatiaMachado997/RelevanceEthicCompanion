"""
LangGraph orchestrator — replaces orchestrator_v2.py.
Entry point: stream_langgraph(user_id, message, model, conversation_id)
"""
from typing import AsyncGenerator, Optional
from langgraph.graph import StateGraph, END
from orchestrator.state import AgentState


def build_graph() -> StateGraph:
    """Build and compile the agent StateGraph. Nodes added in Tasks 4-8."""
    graph = StateGraph(AgentState)
    # Nodes and edges wired in Tasks 4-8
    return graph


async def stream_langgraph(
    user_id: str,
    message: str,
    model: str,
    conversation_id: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """
    Entry point for the LangGraph orchestrator.
    Yields SSE event dicts identical to orchestrator_v2.stream_message().
    NOTE: Raises NotImplementedError — nodes not yet wired (complete Tasks 4-8 first).
    """
    raise NotImplementedError("Nodes not yet wired — complete Tasks 4-8 first")
    yield  # make this a generator
