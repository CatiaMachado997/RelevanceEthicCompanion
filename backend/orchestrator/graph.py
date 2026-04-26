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
    g.add_conditional_edges(
        "intent_classifier",
        _route_after_intent,
        {"deep_research": "deep_research", "tool_planner": "tool_planner"},
    )
    g.add_conditional_edges(
        "tool_planner",
        _route_after_tools,
        {"tool_execution": "tool_execution", "esl_gateway": "esl_gateway"},
    )
    g.add_edge("tool_execution", "esl_gateway")
    g.add_edge("deep_research", "esl_gateway")
    g.add_conditional_edges(
        "esl_gateway",
        _route_after_esl,
        {"response_formatter": "response_formatter", "explain_veto": "explain_veto"},
    )
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
    active_sources: Optional[list] = None,
    force_retrieval: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    Stream SSE events from the LangGraph orchestrator.
    Uses astream_events(version="v2") for true token-level streaming.

    Token flow:
      - on_chat_model_stream events from tool_planner / tool_execution / deep_research
        yield individual tokens as the LLM generates them.
      - ESL decision is attached to the final done event.
      - Tool use/result events are yielded from tool_execution output.
      - Veto explanation tokens come from explain_veto_node output.
    """
    import logging

    logger = logging.getLogger(__name__)

    initial_state: AgentState = {
        "user_id": user_id,
        "message": message,
        "conversation_id": conversation_id,
        "model": model,
        "user_context": {},
        "conversation_history": [],
        "active_sources": active_sources or [],
        "intent": "",
        "tool_calls": [],
        "tool_results": [],
        "esl_decision": None,
        "proposed_content": "",
        "response_text": "",
        "response_events": [],
        "citations": [],
        "document_sources": [],
        "token_count": 0,
        "token_warning": None,
        "pending_tool_confirmation": None,
        "source_context": [],
        "force_retrieval": force_retrieval,
    }
    graph = get_graph()

    # Nodes whose LLM calls generate the final user-visible response
    RESPONSE_NODES = frozenset({"tool_planner", "tool_execution", "deep_research"})

    response_text = ""
    esl_data = {}
    citations: list = []
    document_sources: list = []
    tool_events_yielded = False
    done_yielded = False

    try:
        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event.get("event", "")
            metadata = event.get("metadata", {})
            node = metadata.get("langgraph_node", "")

            # ── True token streaming from LLM calls in content-generating nodes ──
            if kind == "on_chat_model_stream" and node in RESPONSE_NODES:
                chunk = event.get("data", {}).get("chunk")
                if chunk is None:
                    continue
                # Extract text content (skip tool_call chunks)
                content = getattr(chunk, "content", "")
                if isinstance(content, list):
                    # Handle content blocks (e.g. {"type": "text", "text": "..."})
                    content = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in content
                    )
                if isinstance(content, str) and content:
                    response_text += content
                    yield {"event": "token", "token": content}

            # ── Tool use/result events + citations (emitted BEFORE tokens if tools ran) ──
            elif (
                kind == "on_chain_end"
                and node == "tool_execution"
                and not tool_events_yielded
            ):
                tool_events_yielded = True
                raw_output = event.get("data", {}).get("output")
                output = raw_output if isinstance(raw_output, dict) else {}
                for ev in output.get("response_events", []):
                    if ev.get("event") in ("tool_use", "tool_result"):
                        yield ev
                # Capture citation sources for the done event
                citations = output.get("citations", [])
                document_sources = output.get("document_sources", [])

            # ── Token warning ──
            elif kind == "on_chain_end" and node in ("tool_execution", "tool_planner"):
                raw_output = event.get("data", {}).get("output")
                output = raw_output if isinstance(raw_output, dict) else {}
                warning = output.get("token_warning")
                if warning and isinstance(warning, str):
                    yield {"event": "warning", "message": warning}

            # ── ESL decision (capture for done event) ──
            elif kind == "on_chain_end" and node == "esl_gateway":
                raw_output = event.get("data", {}).get("output")
                output = raw_output if isinstance(raw_output, dict) else {}
                decision = output.get("esl_decision")
                if decision:
                    try:
                        esl_data = {
                            "status": decision.status.value,
                            "reason": decision.reason,
                            "violated_values": getattr(decision, "violated_values", []),
                        }
                    except Exception:
                        esl_data = {}

            # ── Veto path — yield veto explanation tokens ──
            elif kind == "on_chain_end" and node == "explain_veto":
                raw_output = event.get("data", {}).get("output")
                output = raw_output if isinstance(raw_output, dict) else {}
                veto_text = output.get("response_text", "")
                if veto_text and not response_text:
                    response_text = veto_text
                    yield {"event": "token", "token": veto_text}

            # ── Graph completion — yield done event ──
            elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                raw_final = event.get("data", {}).get("output")
                final_output = raw_final if isinstance(raw_final, dict) else {}
                # If streaming captured nothing (edge case), fall back to response_text in state
                if not response_text:
                    response_text = final_output.get("response_text", "")
                    if response_text:
                        yield {"event": "token", "token": response_text}

                if not done_yielded:
                    done_yielded = True
                    yield {
                        "event": "done",
                        "esl_decision": esl_data,
                        "citations": citations,
                        "document_sources": document_sources,
                    }

    except Exception as e:
        logger.error(f"stream_langgraph error: {e}", exc_info=True)
        if not done_yielded:
            yield {"event": "error", "message": str(e)}
            yield {"event": "done", "esl_decision": {}}
        return

    if not done_yielded:
        yield {
            "event": "done",
            "esl_decision": esl_data,
            "citations": citations,
            "document_sources": document_sources,
        }

    # Store conversation turns non-blocking
    await _post_stream_store(
        user_id=user_id,
        user_msg=message,
        assistant_msg=response_text,
        conversation_id=conversation_id,
        document_sources=document_sources,
        citations=citations,
    )


async def _post_stream_store(
    user_id: str,
    user_msg: str,
    assistant_msg: str,
    conversation_id: Optional[str],
    document_sources: Optional[list] = None,
    citations: Optional[list] = None,
) -> None:
    """Persist conversation turns to M1 + M2. Non-blocking — errors are logged."""
    import logging

    logger = logging.getLogger(__name__)
    try:
        from orchestrator.nodes.context import get_context_manager

        cm = get_context_manager()
        # Build assistant metadata: only include fields that have content.
        assistant_meta: dict = {}
        if document_sources:
            assistant_meta["document_sources"] = document_sources
        if citations:
            assistant_meta["citations"] = citations

        # Adapt to actual ContextManager API (check what store methods exist)
        if hasattr(cm, "store_conversation_turn"):
            await cm.store_conversation_turn(
                user_id, "user", user_msg, conversation_id=conversation_id
            )
            await cm.store_conversation_turn(
                user_id,
                "assistant",
                assistant_msg,
                conversation_id=conversation_id,
                metadata=assistant_meta or None,
            )
        if hasattr(cm, "store_semantic_memory"):
            try:
                from models.context import SemanticMemoryEntry

                for role, content in [("user", user_msg), ("assistant", assistant_msg)]:
                    entry = SemanticMemoryEntry(
                        user_id=user_id,
                        content=content,
                        source="conversation",
                        metadata={"role": role},
                    )
                    await cm.store_semantic_memory(entry)
            except ImportError:
                pass
    except Exception as e:
        logger.warning(f"Post-stream storage failed (non-blocking): {e}")
