"""LangGraph orchestrator — full wired graph."""
from typing import AsyncGenerator, Optional
from langgraph.graph import StateGraph, END
from orchestrator.state import AgentState
from orchestrator.nodes.context import context_builder_node
from orchestrator.nodes.intent import intent_classifier_node
from orchestrator.nodes.tools import tool_planner_node, tool_execution_node
from orchestrator.nodes.esl import esl_gateway_node
from orchestrator.nodes.response import response_formatter_node, explain_veto_node
from orchestrator.subgraphs.deep_research import deep_research_node
from esl.models import ESLDecisionStatus


def _route_after_esl(state: AgentState) -> str:
    decision = state.get("esl_decision")
    if decision and decision.status == ESLDecisionStatus.VETOED:
        return "explain_veto"
    return "response_formatter"


def _route_after_intent(state: AgentState) -> str:
    """Route deep research intents to the research subgraph."""
    if state.get("intent") == "research_deep":
        return "deep_research"
    return "tool_planner"


def _route_after_tools(state: AgentState) -> str:
    """If ToolPlanner returned tool_calls, execute them; otherwise go to ESL."""
    if state.get("tool_calls"):
        return "tool_execution"
    return "esl_gateway"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("context_builder", context_builder_node)
    g.add_node("intent_classifier", intent_classifier_node)
    g.add_node("tool_planner", tool_planner_node)
    g.add_node("tool_execution", tool_execution_node)
    g.add_node("deep_research", deep_research_node)
    g.add_node("esl_gateway", esl_gateway_node)
    g.add_node("response_formatter", response_formatter_node)
    g.add_node("explain_veto", explain_veto_node)

    g.set_entry_point("context_builder")
    g.add_edge("context_builder", "intent_classifier")
    g.add_conditional_edges("intent_classifier", _route_after_intent,
                            {"deep_research": "deep_research", "tool_planner": "tool_planner"})
    g.add_conditional_edges("tool_planner", _route_after_tools,
                            {"tool_execution": "tool_execution", "esl_gateway": "esl_gateway"})
    g.add_edge("tool_execution", "esl_gateway")
    g.add_edge("deep_research", "esl_gateway")
    g.add_conditional_edges("esl_gateway", _route_after_esl,
                            {"response_formatter": "response_formatter", "explain_veto": "explain_veto"})
    g.add_edge("response_formatter", END)
    g.add_edge("explain_veto", END)
    return g.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


async def stream_langgraph(
    user_id: str,
    message: str,
    model: str = "llama-3.3-70b-versatile",
    conversation_id: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """
    Stream SSE events from the LangGraph orchestrator.

    STREAMING NOTE (Sprint 2a known limitation):
    LangGraph's ainvoke() buffers the full graph run before returning.
    For Sprint 2a, the response appears as a single batch of token events after
    the full LLM call completes — no incremental character streaming.
    The SSE protocol is preserved (token events + done event), so the frontend
    handles it correctly, but the UX shows a delay then the full response at once.
    True token-level streaming via graph.astream_events() will be addressed in Sprint 2b.
    """
    initial_state: AgentState = {
        "user_id": user_id, "message": message, "conversation_id": conversation_id,
        "model": model, "user_context": {}, "conversation_history": [],
        "intent": "", "tool_calls": [], "tool_results": [],
        "esl_decision": None, "proposed_content": "", "response_text": "",
        "response_events": [], "token_count": 0, "token_warning": None,
    }
    graph = get_graph()
    final_state = await graph.ainvoke(initial_state)

    # Check token warning
    if final_state.get("token_warning"):
        yield final_state["token_warning"]

    # Yield tool_use/tool_result events first (from ToolExecution node)
    for event in final_state.get("response_events", []):
        if event.get("event") in ("tool_use", "tool_result"):
            yield event

    # Then yield token + done events (from ResponseFormatter node)
    for event in final_state.get("response_events", []):
        if event.get("event") not in ("tool_use", "tool_result"):
            yield event

    # Store conversation turns after streaming completes
    await _post_stream_store(
        user_id=user_id,
        user_msg=message,
        assistant_msg=final_state.get("response_text", ""),
        conversation_id=conversation_id,
    )


async def _post_stream_store(
    user_id: str,
    user_msg: str,
    assistant_msg: str,
    conversation_id: Optional[str],
) -> None:
    """Persist conversation turns to M1 + M2. Non-blocking — errors are logged."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        from orchestrator.nodes.context import get_context_manager
        cm = get_context_manager()
        # Adapt to actual ContextManager API (check what store methods exist)
        if hasattr(cm, 'store_conversation_turn'):
            await cm.store_conversation_turn(user_id, "user", user_msg, conversation_id=conversation_id)
            await cm.store_conversation_turn(user_id, "assistant", assistant_msg, conversation_id=conversation_id)
        if hasattr(cm, 'store_semantic_memory'):
            try:
                from models.context import SemanticMemoryEntry
                for role, content in [("user", user_msg), ("assistant", assistant_msg)]:
                    entry = SemanticMemoryEntry(
                        user_id=user_id, content=content,
                        source="conversation", metadata={"role": role}
                    )
                    await cm.store_semantic_memory(entry)
            except ImportError:
                pass
    except Exception as e:
        logger.warning(f"Post-stream storage failed (non-blocking): {e}")
