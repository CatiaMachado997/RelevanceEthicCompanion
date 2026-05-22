"""ToolPlanner and ToolExecution — LLM-driven tool selection and execution."""

import asyncio
import json
import logging
import time
from datetime import datetime, UTC
from typing import Any, List, Optional

from pydantic import SecretStr

from orchestrator.state import AgentState
from orchestrator.nodes.context import get_context_manager
from config import settings
from config import settings as _j_settings
from services.safety_preferences import SafetyPreferencesService, SafetyPreferences

logger = logging.getLogger(__name__)


async def _execute_with_retry(tool: Any, params: dict) -> dict:
    """Run one tool invocation; retry once on exception with 200 ms backoff.

    Returns a structured observation dict — never raises.

    Sprint I Task 9.
    """
    t0 = time.perf_counter()
    last_error: Optional[str] = None
    for attempt in (1, 2):
        try:
            result = await tool.ainvoke(params)
            return {
                "status": "ok",
                "result": result,
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "attempts": attempt,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if attempt == 1:
                await asyncio.sleep(0.2)
    return {
        "status": "error",
        "error": last_error or "unknown error",
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "attempts": 2,
    }


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


def _parse_planner_response(response: Any) -> dict:
    """Convert an LLM response into our structured step shape.

    The model's response will have:
      - `content`: a free-form string (the thought, possibly empty)
      - `tool_calls`: structured tool selections from bind_tools()

    We treat any present tool_calls as the step's actions and the content
    as the thought. If there are no tool_calls, this is the terminal
    step — actions = [], and the content becomes proposed_content for
    the response synthesizer (handled outside this fn).

    Sprint I Task 10.
    """
    content = getattr(response, "content", "") or ""
    thought = content if isinstance(content, str) else str(content)
    tool_calls = list(getattr(response, "tool_calls", []) or [])
    actions = [
        {"tool": tc.get("name", ""), "params": tc.get("args", {}) or {}}
        for tc in tool_calls
    ]
    return {"thought": thought.strip(), "actions": actions, "raw_tool_calls": tool_calls}


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
    """Sprint I: ask the LLM which tool(s) to call this step.

    Emits {thought, actions: [...]} per step. Empty actions = exit loop.
    Manages the planner_runs row lifecycle.
    """
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
        messages.append(
            HumanMessage(content=h["content"])
            if h["role"] == "user"
            else AIMessage(content=h["content"])
        )
    messages.append(HumanMessage(content=state["message"]))

    # On a replan iteration, surface the running plan trace so the
    # planner can see prior thoughts + actions + observations.
    plan_steps: list = list(state.get("plan_steps") or [])
    if plan_steps:
        messages.append(
            SystemMessage(
                content=(
                    "Plan so far (your prior thoughts, actions, and what each tool returned):\n"
                    + json.dumps(plan_steps, default=str)[:6000]
                    + "\n\nIf you have everything you need, respond with no further tool calls."
                )
            )
        )

    # Lazy import to keep tests fast and avoid circulars
    from services.planner_runs import PlannerRunsService

    # First invocation: create the planner_runs parent row.
    planner_run_id = state.get("planner_run_id") or ""
    if not planner_run_id:
        planner_run_id = PlannerRunsService().create(
            user_id=user_id,
            conversation_id=state.get("conversation_id"),
            intent=state.get("intent") or "chat",
        )

    response = await llm_with_tools.ainvoke(messages)
    parsed = _parse_planner_response(response)

    # `/ask` slash command — force a search_documents action on step 1 only.
    if state.get("force_retrieval") and not plan_steps:
        already = any(a["tool"] == "search_documents" for a in parsed["actions"])
        if not already:
            parsed["actions"].insert(
                0,
                {"tool": "search_documents", "params": {"query": state["message"], "k": 5}},
            )
            # Also reflect into raw_tool_calls so downstream legacy paths see it
            parsed["raw_tool_calls"].insert(
                0,
                {
                    "name": "search_documents",
                    "args": {"query": state["message"], "k": 5},
                    "id": "forced_search_documents",
                },
            )

    next_step_index = len(plan_steps) + 1
    step = {
        "step": next_step_index,
        "thought": parsed["thought"],
        "actions": parsed["actions"],
        "observations": [],  # filled in by tool_execution_node
        "started_at": datetime.now(UTC).isoformat(),
    }
    plan_steps.append(step)

    # Maintain legacy tool_calls field so downstream code keeps working:
    legacy_tool_calls = parsed["raw_tool_calls"]
    proposed = parsed["thought"] if not parsed["actions"] else ""

    return {
        "tool_calls": legacy_tool_calls,
        "proposed_content": proposed,
        "planner_step": next_step_index,
        "plan_steps": plan_steps,
        "planner_run_id": planner_run_id,
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
    planner_run_id: Optional[str] = None,
    step_index: Optional[int] = None,
    action_index: Optional[int] = None,
) -> None:
    """Best-effort tool_call_events insert. Never raises.

    Sprint I — added planner_run_id / step_index / action_index breadcrumbs.
    """
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
            planner_run_id=planner_run_id,
            step_index=step_index,
            action_index=action_index,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("tool telemetry record failed for %s: %s", tool_name, exc)


async def tool_execution_node(state: AgentState) -> dict:
    """Sprint I: execute the latest plan step's actions in parallel.

    For each action:
      - Marketplace tools still pass through ESLToolGate (VETO / PENDING).
      - Other actions run via _execute_with_retry.
    Per-action observations are appended to the current step.
    Each action is also recorded in tool_call_events with the
    planner_run_id, step_index, action_index breadcrumbs.
    """
    from langchain_core.messages import HumanMessage
    from langchain_groq import ChatGroq
    from services.langchain_tools import create_langchain_tools
    from orchestrator.token_tracker import estimate_tokens, check_token_warning

    cm = get_context_manager()
    user_id = state["user_id"]
    conversation_id = state.get("conversation_id")
    planner_run_id = state.get("planner_run_id") or None
    plan_steps: list = list(state.get("plan_steps") or [])
    current_step = plan_steps[-1] if plan_steps else None
    step_index = current_step["step"] if current_step else 0
    step_actions = current_step["actions"] if current_step else []

    document_sources: list = list(state.get("document_sources") or [])
    tools = await create_langchain_tools(
        cm,
        user_id,
        active_sources=state.get("active_sources") or [],
        citation_collector=document_sources,
    )
    tool_map = {t.name: t for t in tools}

    # Sprint J — load the user's layered safety preferences once per
    # step. The result is the same throughout the step's execution.
    if _j_settings.STREAMING_REASONING_ENABLED:
        safety_prefs = SafetyPreferencesService().load_for_user(user_id)
    else:
        safety_prefs = SafetyPreferences(safe_mode_enabled=False)

    llm = ChatGroq(
        model=state.get("model", "llama-3.3-70b-versatile"),
        api_key=SecretStr(settings.GROQ_API_KEY),
    )

    results: list = list(state.get("tool_results") or [])
    events: list = []
    pending_confirmation = None

    parallel_actions: list = []
    sequential_actions: list = []

    for ai, action in enumerate(step_actions):
        tool_name = action.get("tool", "")
        if tool_name not in tool_map:
            results.append({"tool": tool_name, "result": "Tool not found"})
            obs = {"status": "error", "error": "Tool not found", "latency_ms": 0, "attempts": 1}
            if current_step is not None:
                current_step["observations"].append(obs)
            _record_telemetry(
                user_id, conversation_id, tool_name, action.get("params", {}),
                "Tool not found", status="error", latency_ms=0,
                error_message="Tool not found",
                planner_run_id=planner_run_id, step_index=step_index, action_index=ai,
            )
            continue

        t = tool_map[tool_name]
        meta = getattr(t, "metadata", {}) or {}
        category = getattr(t, "category", "write-external")
        needs_confirm = safety_prefs.should_confirm(
            tool_name=tool_name, category=category
        )
        if meta.get("tool_id") and meta.get("action_name"):
            # Marketplace tool: always sequential due to its own ESL gate.
            sequential_actions.append((ai, action, t, category, needs_confirm))
        elif needs_confirm:
            # User-flagged read tool: also goes sequential — we pause per action.
            sequential_actions.append((ai, action, t, category, True))
        else:
            parallel_actions.append((ai, action, t, category, False))
        events.append({"event": "tool_use", "tool": tool_name})

    # --- Parallel fan-out for read-only tools ---
    if parallel_actions:
        obs_list = await asyncio.gather(
            *[_execute_with_retry(t, a.get("params", {})) for _, a, t, _c, _n in parallel_actions],
            return_exceptions=False,
        )
        for (ai, action, t, _category, _needs), obs in zip(parallel_actions, obs_list):
            tool_name = action["tool"]
            params = action.get("params", {})
            if obs["status"] == "ok":
                results.append({"tool": tool_name, "result": str(obs["result"])})
                events.append({"event": "tool_result", "tool": tool_name})
                telemetry_output: Any = (
                    obs["result"] if isinstance(obs["result"], (dict, list))
                    else str(obs["result"])
                )
                trace = getattr(t, "last_trace", None)
                if tool_name == "search_documents" and trace is not None:
                    telemetry_output = {"result": str(obs["result"]), "trace": trace}
                _record_telemetry(
                    user_id, conversation_id, tool_name, params,
                    telemetry_output, status="success",
                    latency_ms=obs["latency_ms"],
                    planner_run_id=planner_run_id, step_index=step_index, action_index=ai,
                )
            else:
                results.append({"tool": tool_name, "result": f"Error: {obs['error']}"})
                _record_telemetry(
                    user_id, conversation_id, tool_name, params,
                    f"Error: {obs['error']}", status="error",
                    latency_ms=obs["latency_ms"],
                    error_message=obs["error"],
                    planner_run_id=planner_run_id, step_index=step_index, action_index=ai,
                )
            if current_step is not None:
                current_step["observations"].append(obs)

    # --- Sequential execution for marketplace-gated tools ---
    for ai, action, t, category, needs_confirm in sequential_actions:
        tool_name = action["tool"]
        tool_input = action.get("params", {})
        meta = getattr(t, "metadata", {}) or {}

        # Sprint J — for non-marketplace tools whose category/tool/master
        # preference requires confirmation, pause via LangGraph interrupt().
        # Marketplace tools have their own ESL gate further down — we
        # don't double-gate them.
        if needs_confirm and not (meta.get("tool_id") and meta.get("action_name")):
            from langgraph.types import interrupt

            decision = interrupt({
                "kind": "user_confirmation",
                "step": step_index,
                "action_index": ai,
                "tool": tool_name,
                "category": category,
                "params": tool_input,
                "reason": safety_prefs.explain_reason(
                    tool_name=tool_name, category=category
                ),
            })
            # On resume, `decision` is whatever was passed to Command(resume=...).
            chosen = (decision or {}).get("action", "approve")
            if chosen == "cancel":
                obs = {"status": "cancelled", "latency_ms": 0, "attempts": 0}
                if current_step is not None:
                    current_step["observations"].append(obs)
                results.append({"tool": tool_name, "result": "Cancelled by user."})
                events.append({"event": "tool_cancelled", "tool": tool_name})
                # Stop processing further actions in this step.
                break
            if chosen == "skip":
                obs = {
                    "status": "skipped", "reason": "user",
                    "latency_ms": 0, "attempts": 0,
                }
                if current_step is not None:
                    current_step["observations"].append(obs)
                results.append({"tool": tool_name, "result": "Skipped by user."})
                events.append({"event": "tool_skipped", "tool": tool_name})
                continue
            if chosen == "approve" and (decision or {}).get("trust"):
                # "Trust this tool from now on" — clear ONLY the per-tool
                # row. Higher layers (master / category) remain.
                SafetyPreferencesService().delete_tool(user_id, tool_name=tool_name)
            # approve (with or without trust) — execute the tool now and
            # skip the marketplace ESL gate below (this is NOT a marketplace tool).
            obs = await _execute_with_retry(t, tool_input)
            if obs["status"] == "ok":
                results.append({"tool": tool_name, "result": str(obs["result"])})
                events.append({"event": "tool_result", "tool": tool_name})
                _record_telemetry(
                    user_id, conversation_id, tool_name, tool_input,
                    obs["result"] if isinstance(obs["result"], (dict, list)) else str(obs["result"]),
                    status="success", latency_ms=obs["latency_ms"],
                    planner_run_id=planner_run_id, step_index=step_index, action_index=ai,
                )
            else:
                results.append({"tool": tool_name, "result": f"Error: {obs['error']}"})
                _record_telemetry(
                    user_id, conversation_id, tool_name, tool_input,
                    f"Error: {obs['error']}", status="error", latency_ms=obs["latency_ms"],
                    error_message=obs["error"],
                    planner_run_id=planner_run_id, step_index=step_index, action_index=ai,
                )
            if current_step is not None:
                current_step["observations"].append(obs)
            continue

        tool_id = meta["tool_id"]
        action_name = meta["action_name"]
        risk_level = meta.get("risk_level", "medium")
        from esl.tool_gate import ESLToolGate, GateResult

        gate = ESLToolGate()
        preview = f"{tool_name}: {json.dumps(tool_input)[:200]}"
        decision = await gate.check(
            user_id=user_id, tool_id=tool_id, action_name=action_name,
            risk_level=risk_level, preview=preview,
        )
        if decision.status == GateResult.VETOED:
            results.append({"tool": tool_name, "result": "Action not permitted by user settings."})
            events.append({"event": "tool_vetoed", "tool": tool_name})
            await _audit_tool_action(user_id, tool_id, action_name, "VETOED", "User denied this action")
            obs = {"status": "error", "error": "vetoed", "latency_ms": 0, "attempts": 1}
            if current_step is not None:
                current_step["observations"].append(obs)
            _record_telemetry(
                user_id, conversation_id, tool_name, tool_input,
                "Action not permitted by user settings.",
                status="vetoed", latency_ms=0, esl_decision="VETOED",
                planner_run_id=planner_run_id, step_index=step_index, action_index=ai,
            )
            continue
        if decision.status == GateResult.PENDING_CONFIRMATION:
            pending_confirmation = {
                "tool_id": tool_id, "action_name": action_name,
                "tool_name": tool_name, "preview": decision.preview,
                "params": tool_input, "risk_level": risk_level,
            }
            events.append({
                "event": "tool_pending_confirmation", "tool": tool_name,
                "tool_id": tool_id, "tool_name": tool_name,
                "action_name": action_name, "preview": decision.preview,
            })
            results.append({"tool": tool_name, "result": f"Awaiting your confirmation: {decision.preview}"})
            obs = {"status": "pending", "latency_ms": 0, "attempts": 1}
            if current_step is not None:
                current_step["observations"].append(obs)
            _record_telemetry(
                user_id, conversation_id, tool_name, tool_input,
                {"preview": decision.preview}, status="pending_confirmation",
                latency_ms=0,
                planner_run_id=planner_run_id, step_index=step_index, action_index=ai,
            )
            continue

        obs = await _execute_with_retry(t, tool_input)
        if obs["status"] == "ok":
            results.append({"tool": tool_name, "result": str(obs["result"])})
            events.append({"event": "tool_result", "tool": tool_name})
            await _audit_tool_action(user_id, tool_id, action_name, "APPROVED", "Marketplace tool executed")
            _record_telemetry(
                user_id, conversation_id, tool_name, tool_input,
                obs["result"] if isinstance(obs["result"], (dict, list)) else str(obs["result"]),
                status="success", latency_ms=obs["latency_ms"], esl_decision="APPROVED",
                planner_run_id=planner_run_id, step_index=step_index, action_index=ai,
            )
        else:
            results.append({"tool": tool_name, "result": f"Error: {obs['error']}"})
            _record_telemetry(
                user_id, conversation_id, tool_name, tool_input,
                f"Error: {obs['error']}", status="error", latency_ms=obs["latency_ms"],
                error_message=obs["error"],
                planner_run_id=planner_run_id, step_index=step_index, action_index=ai,
            )
        if current_step is not None:
            current_step["observations"].append(obs)

    # Step done — capture timing
    if current_step is not None and "duration_ms" not in current_step:
        try:
            start = datetime.fromisoformat(current_step["started_at"])
            current_step["duration_ms"] = int(
                (datetime.now(UTC) - start).total_seconds() * 1000
            )
        except Exception:
            current_step["duration_ms"] = 0

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
        "plan_steps": plan_steps,
    }
