"""AgentState — typed state dict carried through every LangGraph node."""

from typing import TypedDict, Optional
from esl.models import ESLDecision


class AgentState(TypedDict):
    # Input
    user_id: str
    message: str
    conversation_id: Optional[str]
    model: str

    # Context
    user_context: dict  # goals, values, focus_mode, recent_memory
    conversation_history: list  # [{role, content}, ...]

    # Intent
    intent: str  # "chat" | "research_quick" | "plan" | "search" | "file_question"

    # Source filtering — empty list means all sources enabled
    active_sources: list  # e.g. ["calendar", "goals"] — empty = all

    # Tool execution
    tool_calls: list  # tool calls planned by ToolPlanner
    tool_results: list  # results from ToolExecution

    # ESL
    esl_decision: Optional[ESLDecision]
    proposed_content: str  # the response text before ESL evaluation

    # Output
    response_text: str  # final response to stream to user
    response_events: list  # list of SSE event dicts to yield

    # Citations — sources consulted by tool calls
    citations: list  # [{"tool": str, "label": str, "icon": str}, ...]

    # Document sources — per-chunk citations from search_documents (RAG)
    # [{chunk_uuid, document_id, filename, chunk_index, snippet, score}, ...]
    document_sources: list

    # Token tracking
    token_count: int
    token_warning: Optional[dict]

    # Marketplace tool awaiting user confirmation
    pending_tool_confirmation: Optional[dict]  # {tool_id, action_name, preview, params}

    # Source items context from synced integrations
    source_context: list  # [{source_type, source_item_type, title, body, item_at}]

    # When True, planner injects a search_documents tool call regardless of
    # the LLM's judgement. Set by the `/ask` slash command in the UI.
    force_retrieval: bool

    # Multi-step planner loop bookkeeping. The planner increments
    # `planner_step` on each invocation. The conditional router after
    # `tool_execution_node` short-circuits to ESL once
    # `planner_step >= max_planner_steps`, preventing runaway loops.
    planner_step: int
    max_planner_steps: int
