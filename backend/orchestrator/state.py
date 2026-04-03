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
    user_context: dict          # goals, values, focus_mode, recent_memory
    conversation_history: list  # [{role, content}, ...]

    # Intent
    intent: str                 # "chat" | "research_quick" | "plan" | "search" | "file_question"

    # Tool execution
    tool_calls: list            # tool calls planned by ToolPlanner
    tool_results: list          # results from ToolExecution

    # ESL
    esl_decision: Optional[ESLDecision]
    proposed_content: str       # the response text before ESL evaluation

    # Output
    response_text: str          # final response to stream to user
    response_events: list       # list of SSE event dicts to yield

    # Citations — sources consulted by tool calls
    citations: list  # [{"tool": str, "label": str, "icon": str}, ...]

    # Token tracking
    token_count: int
    token_warning: Optional[dict]
