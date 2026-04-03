"""ToolPlanner and ToolExecution — LLM-driven tool selection and execution."""
import json
import logging
from orchestrator.state import AgentState
from orchestrator.nodes.context import get_context_manager
from config import settings

logger = logging.getLogger(__name__)

# Maps tool name → display metadata. None means the tool is a write tool (no citation shown).
_TOOL_CITATION_META: dict = {
    "query_calendar": {"label": "Google Calendar", "icon": "calendar"},
    "query_memory":   {"label": "Memory",          "icon": "memory"},
    "get_user_goals": {"label": "Goals",            "icon": "target"},
    "web_search":     {"label": "Web Search",       "icon": "globe"},
    "create_note":    None,  # write tool — omit from citations
}


def _build_citations(results: list) -> list:
    """Derive citation pills from executed tool results (read tools only)."""
    seen: set = set()
    citations = []
    for r in results:
        tool = r.get("tool", "")
        if tool in seen:
            continue
        seen.add(tool)
        meta = _TOOL_CITATION_META.get(tool)
        if meta is None:
            continue  # write tool or unknown — skip
        result_text = r.get("result", "")
        # Skip tools that errored out or returned nothing useful
        if result_text.startswith("Error") or result_text.startswith("No "):
            continue
        citations.append({"tool": tool, "label": meta["label"], "icon": meta["icon"]})
    return citations


def _build_system_prompt(state: AgentState) -> str:
    ctx = state.get("user_context", {})
    goals = ctx.get("active_goals", [])
    values = ctx.get("user_values", [])
    return (
        "You are Ethic Companion, a personal work assistant that respects the user's values and boundaries.\n"
        f"User's active goals: {goals}\n"
        f"User's values: {values}\n"
        "Answer helpfully and concisely. Use tools when you need live data."
    )


async def tool_planner_node(state: AgentState) -> dict:
    """Ask the LLM which tools to call given the current message + context."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_groq import ChatGroq
    from services.langchain_tools import create_langchain_tools

    cm = get_context_manager()
    user_id = state["user_id"]
    tools = create_langchain_tools(cm, user_id)
    llm = ChatGroq(
        model=state.get("model", "llama-3.3-70b-versatile"),
        api_key=settings.GROQ_API_KEY,
    )
    llm_with_tools = llm.bind_tools(tools)

    messages = [SystemMessage(content=_build_system_prompt(state))]
    for h in state.get("conversation_history", []):
        messages.append(
            HumanMessage(content=h["content"])
            if h["role"] == "user"
            else SystemMessage(content=h["content"])
        )
    messages.append(HumanMessage(content=state["message"]))

    response = await llm_with_tools.ainvoke(messages)
    tool_calls = getattr(response, "tool_calls", []) or []
    proposed = response.content if not tool_calls else ""
    return {"tool_calls": tool_calls, "proposed_content": proposed}


async def tool_execution_node(state: AgentState) -> dict:
    """Execute tool calls and synthesize a final response."""
    from langchain_core.messages import HumanMessage
    from langchain_groq import ChatGroq
    from services.langchain_tools import create_langchain_tools
    from orchestrator.token_tracker import estimate_tokens, check_token_warning

    cm = get_context_manager()
    user_id = state["user_id"]
    tools = create_langchain_tools(cm, user_id)
    tool_map = {t.name: t for t in tools}
    llm = ChatGroq(
        model=state.get("model", "llama-3.3-70b-versatile"),
        api_key=settings.GROQ_API_KEY,
    )

    results = []
    events = []
    for tc in state.get("tool_calls", []):
        tool_name = tc.get("name", "")
        tool_input = tc.get("args", {})
        events.append({"event": "tool_use", "tool": tool_name})
        if tool_name in tool_map:
            try:
                result = await tool_map[tool_name].ainvoke(tool_input)
                results.append({"tool": tool_name, "result": str(result)})
                events.append({"event": "tool_result", "tool": tool_name})
            except Exception as e:
                results.append({"tool": tool_name, "result": f"Error: {e}"})
        else:
            results.append({"tool": tool_name, "result": "Tool not found"})

    if results:
        synthesis_prompt = (
            f"User asked: {state['message']}\n"
            f"Tool results: {json.dumps(results)}\n"
            "Provide a helpful, concise response based on these results."
        )
        response = await llm.ainvoke([HumanMessage(content=synthesis_prompt)])
        proposed = response.content
    else:
        proposed = state.get("proposed_content", "")

    tokens_used = estimate_tokens(state.get("message", "")) + estimate_tokens(proposed)
    warning = check_token_warning(state["user_id"], tokens_used)
    return {
        "tool_results": results,
        "proposed_content": proposed,
        "response_events": events,
        "citations": _build_citations(results),
        "token_count": state.get("token_count", 0) + tokens_used,
        "token_warning": warning,
    }
