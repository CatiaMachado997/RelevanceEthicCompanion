"""ToolPlanner and ToolExecution — LLM-driven tool selection and execution."""

import json
import logging
import time
from datetime import datetime, UTC
from typing import List, Optional

from pydantic import SecretStr

from orchestrator.state import AgentState
from orchestrator.nodes.context import get_context_manager
from config import settings

logger = logging.getLogger(__name__)


async def _audit_tool_action(
    user_id: str,
    tool_id: str,
    action_name: str,
    status: str,
    reason: str,
) -> None:
    """Best-effort ESL audit log for marketplace tool actions."""
    try:
        from esl.audit import ESLAuditLogger
        from esl.models import (
            ProposedAction,
            ESLDecision,
            ESLDecisionStatus,
            ActionType,
            UrgencyLevel,
        )

        # TODO: Add ActionType.TOOL_EXECUTION to the enum once ESL models are extended
        # For now, map to the closest existing action type
        action_type_map = {
            "google_calendar": ActionType.CALENDAR_WRITE,
            "gmail": ActionType.EMAIL_SEND,
            "slack": ActionType.SLACK_SEND,
        }
        resolved_type = ActionType.CONTENT_GENERATION  # fallback
        for key, at in action_type_map.items():
            if key in tool_id.lower():
                resolved_type = at
                break

        proposed = ProposedAction(
            action_type=resolved_type,
            content_type=f"tool:{tool_id}/{action_name}",
            urgency=UrgencyLevel.MEDIUM,
            content=f"Marketplace tool action: {action_name}",
            metadata={"tool_id": tool_id, "action_name": action_name},
        )
        decision = ESLDecision(
            status=ESLDecisionStatus(status),
            reason=reason,
            confidence=1.0,
            timestamp=datetime.now(UTC),
        )
        audit_logger = ESLAuditLogger()
        await audit_logger.log_decision(
            user_id=user_id,
            proposed_action=proposed,
            decision=decision,
            context_snapshot={"source": "tool_execution_node", "tool_id": tool_id},
        )
    except Exception:
        pass  # audit failure must never break execution


# Maps tool name → display metadata. None means the tool is a write tool (no citation shown).
_TOOL_CITATION_META: dict = {
    "query_calendar": {"label": "Google Calendar", "icon": "calendar"},
    "query_memory": {"label": "Memory", "icon": "memory"},
    "get_user_goals": {"label": "Goals", "icon": "target"},
    "web_search": {"label": "Web Search", "icon": "globe"},
    "search_documents": {"label": "Documents", "icon": "file-text"},
    "create_note": None,  # write tool — omit from citations
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
    snapshot = ctx.get("snapshot", {})

    # Format goals
    goal_lines = (
        "\n".join(
            f"  - {g.get('title', g) if isinstance(g, dict) else str(g)}"
            for g in goals[:5]
        )
        or "  (none)"
    )

    # Format values
    value_lines = (
        "\n".join(
            f"  - {v.get('value', v) if isinstance(v, dict) else str(v)}"
            for v in values[:5]
        )
        or "  (none)"
    )

    # Format snapshot sections (only when non-empty)
    snapshot_sections = []

    events = snapshot.get("upcoming_events", [])
    if events:
        event_lines = "\n".join(
            f"  - {e['title']} at {e['start_time'][:16] if e.get('start_time') else 'TBD'}"
            + (f" ({e['location']})" if e.get("location") else "")
            for e in events[:5]
        )
        snapshot_sections.append(f"Today's events:\n{event_lines}")

    tasks = snapshot.get("tasks_due_soon", [])
    if tasks:
        task_lines = "\n".join(
            f"  - {t['title']} (due {t['due_date'][:10] if t.get('due_date') else 'soon'}"
            + (f", project: {t['project_title']}" if t.get("project_title") else "")
            + ")"
            for t in tasks[:5]
        )
        snapshot_sections.append(f"Tasks due soon:\n{task_lines}")

    overdue = snapshot.get("overdue_count", 0)
    if overdue:
        snapshot_sections.append(f"Overdue tasks: {overdue}")

    projects = snapshot.get("active_projects", [])
    if projects:
        project_lines = "\n".join(
            f"  - {p['title']} ({p['open_tasks']} open, {p['done_tasks']} done)"
            for p in projects[:5]
        )
        snapshot_sections.append(f"Active projects:\n{project_lines}")

    # Source context from synced integrations
    source_context = ctx.get("source_context", [])
    if source_context:
        cal_items = [
            i for i in source_context if i.get("source_item_type") == "calendar_event"
        ]
        email_items = [
            i for i in source_context if i.get("source_item_type") == "email"
        ]
        source_parts = []
        if cal_items:
            cal_lines = "\n".join(
                f"  - {item['title']} · {(item.get('item_at') or '')[:16]}"
                for item in cal_items[:10]
            )
            source_parts.append(f"[Calendar — next 7 days]\n{cal_lines}")
        if email_items:
            email_lines = "\n".join(
                f"  - {item['title']} ({(item.get('item_at') or '')[:16]})"
                for item in email_items[:10]
            )
            source_parts.append(f"[Recent emails]\n{email_lines}")
        if source_parts:
            snapshot_sections.append(
                "## Your current context\n\n" + "\n\n".join(source_parts)
            )

    pressure = snapshot.get("calendar_pressure", "")
    if pressure and pressure != "light":
        snapshot_sections.append(f"Calendar pressure: {pressure}")

    context_block = "\n\n".join(snapshot_sections)

    prompt = (
        "You are Ethic Companion, a personal work assistant that respects the user's values and boundaries.\n\n"
        f"User's active goals:\n{goal_lines}\n\n"
        f"User's values:\n{value_lines}"
    )
    if context_block:
        prompt += f"\n\n{context_block}"
    prompt += "\n\nAnswer helpfully and concisely. Use tools when you need live data beyond what's shown above."
    prompt += (
        "\n\nWhen the user asks a knowledge-recall question about their own "
        "workspace — e.g. what someone said, decisions made, past emails or "
        "threads, or 'the latest on' a topic — prefer calling `search_documents` "
        "first rather than answering from training or memory."
    )

    return prompt


async def tool_planner_node(state: AgentState) -> dict:
    """Ask the LLM which tools to call given the current message + context."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_groq import ChatGroq
    from services.langchain_tools import create_langchain_tools

    cm = get_context_manager()
    user_id = state["user_id"]
    tools = await create_langchain_tools(
        cm, user_id, active_sources=state.get("active_sources") or []
    )
    llm = ChatGroq(
        model=state.get("model", "llama-3.3-70b-versatile"),
        api_key=SecretStr(settings.GROQ_API_KEY),
    )
    llm_with_tools = llm.bind_tools(tools)

    from langchain_core.messages import BaseMessage

    messages: List[BaseMessage] = [SystemMessage(content=_build_system_prompt(state))]
    for h in state.get("conversation_history", []):
        # Prior assistant turns must be AIMessage so the LLM treats them as
        # its own past replies (i.e. real conversational memory). Using
        # SystemMessage here mixed prior replies with system instructions
        # and prevented the model from following the conversation thread.
        messages.append(
            HumanMessage(content=h["content"])
            if h["role"] == "user"
            else AIMessage(content=h["content"])
        )
    messages.append(HumanMessage(content=state["message"]))

    # On a replan iteration, surface results from earlier tool calls so the
    # planner can decide whether further tools are needed.
    prior_results = state.get("tool_results") or []
    if prior_results:
        messages.append(
            SystemMessage(
                content=(
                    "Tools already executed this turn (results available "
                    "for follow-up planning):\n"
                    + json.dumps(prior_results)[:4000]
                    + "\n\nIf you have everything you need, respond with no "
                    "further tool calls."
                )
            )
        )

    response = await llm_with_tools.ainvoke(messages)
    tool_calls = list(getattr(response, "tool_calls", []) or [])
    proposed = response.content if not tool_calls else ""

    # `/ask` slash command: force a search_documents call so the user can audit
    # which chunks the answer was grounded in regardless of the planner's choice.
    if state.get("force_retrieval"):
        already = any(tc.get("name") == "search_documents" for tc in tool_calls)
        if not already:
            tool_calls.insert(
                0,
                {
                    "name": "search_documents",
                    "args": {"query": state["message"], "k": 5},
                    "id": "forced_search_documents",
                },
            )
            proposed = ""

    next_step = state.get("planner_step", 0) + 1
    return {
        "tool_calls": tool_calls,
        "proposed_content": proposed,
        "planner_step": next_step,
    }


def _record_telemetry(
    user_id: str,
    conversation_id: Optional[str],
    tool_name: str,
    tool_input: dict,
    output: object,
    status: str,
    latency_ms: int,
    error_message: Optional[str] = None,
    esl_decision: Optional[str] = None,
) -> None:
    """Best-effort tool_call_events insert. Never raises."""
    try:
        from services.tool_telemetry import ToolTelemetryService

        if isinstance(output, (dict, list)) or output is None:
            payload: object = output
        else:
            payload = str(output)[:4000]
        ToolTelemetryService().record_tool_call(
            user_id=user_id,
            tool_name=tool_name,
            source="chat",
            source_ref=conversation_id,
            input=tool_input or {},
            output=payload,
            status=status,
            error_message=error_message,
            esl_decision=esl_decision,
            latency_ms=latency_ms,
        )
    except Exception as exc:  # noqa: BLE001 — defensive; telemetry must not break flow
        logger.warning("tool telemetry record failed for %s: %s", tool_name, exc)


async def tool_execution_node(state: AgentState) -> dict:
    """Execute tool calls and synthesize a final response."""
    from langchain_core.messages import HumanMessage
    from langchain_groq import ChatGroq
    from services.langchain_tools import create_langchain_tools
    from orchestrator.token_tracker import estimate_tokens, check_token_warning

    cm = get_context_manager()
    user_id = state["user_id"]
    conversation_id = state.get("conversation_id")
    # Mutable list passed into search_documents — populated when the tool runs.
    document_sources: list = list(state.get("document_sources") or [])
    tools = await create_langchain_tools(
        cm,
        user_id,
        active_sources=state.get("active_sources") or [],
        citation_collector=document_sources,
    )
    tool_map = {t.name: t for t in tools}
    llm = ChatGroq(
        model=state.get("model", "llama-3.3-70b-versatile"),
        api_key=SecretStr(settings.GROQ_API_KEY),
    )

    # Accumulate across replans so the synthesis step (and downstream
    # citation builder) sees every tool that ran this turn.
    results: list = list(state.get("tool_results") or [])
    events: list = []
    pending_confirmation = None

    for tc in state.get("tool_calls", []):
        tool_name = tc.get("name", "")
        tool_input = tc.get("args", {})
        events.append({"event": "tool_use", "tool": tool_name})

        if tool_name not in tool_map:
            results.append({"tool": tool_name, "result": "Tool not found"})
            _record_telemetry(
                user_id,
                conversation_id,
                tool_name,
                tool_input,
                "Tool not found",
                status="error",
                latency_ms=0,
                error_message="Tool not found",
            )
            continue

        t = tool_map[tool_name]
        meta = getattr(t, "metadata", {}) or {}
        tool_id = meta.get("tool_id")
        action_name = meta.get("action_name")
        risk_level = meta.get("risk_level", "medium")

        # Only gate marketplace tools (they have tool_id in metadata)
        if tool_id and action_name:
            from esl.tool_gate import ESLToolGate, GateResult

            gate = ESLToolGate()
            preview = f"{tool_name}: {json.dumps(tool_input)[:200]}"
            decision = await gate.check(
                user_id=user_id,
                tool_id=tool_id,
                action_name=action_name,
                risk_level=risk_level,
                preview=preview,
            )
            if decision.status == GateResult.VETOED:
                results.append(
                    {
                        "tool": tool_name,
                        "result": "Action not permitted by user settings.",
                    }
                )
                events.append({"event": "tool_vetoed", "tool": tool_name})
                await _audit_tool_action(
                    user_id, tool_id, action_name, "VETOED", "User denied this action"
                )
                _record_telemetry(
                    user_id,
                    conversation_id,
                    tool_name,
                    tool_input,
                    "Action not permitted by user settings.",
                    status="vetoed",
                    latency_ms=0,
                    esl_decision="VETOED",
                )
                continue
            if decision.status == GateResult.PENDING_CONFIRMATION:
                pending_confirmation = {
                    "tool_id": tool_id,
                    "action_name": action_name,
                    "tool_name": tool_name,
                    "preview": decision.preview,
                    "params": tool_input,
                    "risk_level": risk_level,
                }
                events.append(
                    {
                        "event": "tool_pending_confirmation",
                        "tool": tool_name,
                        "tool_id": tool_id,
                        "tool_name": tool_name,
                        "action_name": action_name,
                        "preview": decision.preview,
                    }
                )
                results.append(
                    {
                        "tool": tool_name,
                        "result": f"Awaiting your confirmation: {decision.preview}",
                    }
                )
                _record_telemetry(
                    user_id,
                    conversation_id,
                    tool_name,
                    tool_input,
                    {"preview": decision.preview},
                    status="pending_confirmation",
                    latency_ms=0,
                )
                continue

        t0 = time.perf_counter()
        try:
            result = await t.ainvoke(tool_input)
            t1 = time.perf_counter()
            results.append({"tool": tool_name, "result": str(result)})
            events.append({"event": "tool_result", "tool": tool_name})
            if tool_id and action_name:
                await _audit_tool_action(
                    user_id,
                    tool_id,
                    action_name,
                    "APPROVED",
                    "Marketplace tool executed",
                )
            _record_telemetry(
                user_id,
                conversation_id,
                tool_name,
                tool_input,
                result if isinstance(result, (dict, list)) else str(result),
                status="success",
                latency_ms=int((t1 - t0) * 1000),
                esl_decision="APPROVED" if (tool_id and action_name) else None,
            )
        except Exception as e:
            t1 = time.perf_counter()
            results.append({"tool": tool_name, "result": f"Error: {e}"})
            _record_telemetry(
                user_id,
                conversation_id,
                tool_name,
                tool_input,
                f"Error: {e}",
                status="error",
                latency_ms=int((t1 - t0) * 1000),
                error_message=str(e),
            )

    # Clear consumed tool_calls so the next planner pass starts fresh.
    cleared_tool_calls: list = []

    if results:
        synthesis_prompt = (
            f"User asked: {state['message']}\n"
            f"Tool results: {json.dumps(results)}\n"
            "Provide a helpful, concise response based on these results."
        )
        response = await llm.ainvoke([HumanMessage(content=synthesis_prompt)])
        raw = response.content
        proposed = raw if isinstance(raw, str) else str(raw)
    else:
        proposed = state.get("proposed_content", "")

    tokens_used = estimate_tokens(state.get("message", "")) + estimate_tokens(proposed)
    warning = check_token_warning(state["user_id"], tokens_used)
    return {
        "tool_calls": cleared_tool_calls,
        "tool_results": results,
        "proposed_content": proposed,
        "response_events": events,
        "citations": _build_citations(results),
        "document_sources": document_sources,
        "token_count": state.get("token_count", 0) + tokens_used,
        "token_warning": warning,
        "pending_tool_confirmation": pending_confirmation,
    }
