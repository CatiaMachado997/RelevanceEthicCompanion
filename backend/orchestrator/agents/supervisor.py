"""Supervisor — routes user requests to specialised worker agents."""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from orchestrator.agents.research import build_agent as build_research
from orchestrator.agents.calendar import build_agent as build_calendar
from orchestrator.agents.goals import build_agent as build_goals
from orchestrator.agents.document import build_agent as build_document
from orchestrator.agents.connectors import build_agent as build_connectors

logger = logging.getLogger(__name__)

SUPERVISOR_SYSTEM_PROMPT = (
    "You are the Ethic Companion Supervisor. Your only job is to decide which specialist "
    "agent(s) to call to answer the user's request. Never answer directly — always delegate.\n\n"
    "Agents available:\n"
    "- research_agent: web searches, deep research, current events\n"
    "- calendar_agent: schedule, events, time management\n"
    "- goals_agent: user goals, values, decision-making alignment\n"
    "- document_agent: questions about uploaded files and documents\n"
    "- connectors_agent: actions in Slack, Gmail, GitHub, Notion (only if user has authorised "
    "those connectors in their active_sources list)\n\n"
    "Rules:\n"
    "1. Never invoke connectors_agent for a connector not in the user's active_sources.\n"
    "2. For ambiguous requests, prefer research_agent.\n"
    "3. You may call multiple agents in sequence when a request spans domains.\n"
    "4. Synthesise the agents' outputs into one coherent final answer."
)


def build_supervisor(
    routing_llm: Any,
    worker_llm: Any,
    checkpointer: Any = None,
    user_id: str = "",
    context_manager: Any = None,
    connected_tool_ids: set[str] | None = None,
):
    """Return a compiled Supervisor graph with all five worker agents."""
    if checkpointer is None:
        checkpointer = MemorySaver()

    # Build the five worker agents
    agent_specs = [
        ("research_agent", build_research(llm=worker_llm, checkpointer=checkpointer, user_id=user_id, context_manager=context_manager)),
        ("calendar_agent", build_calendar(llm=worker_llm, checkpointer=checkpointer, user_id=user_id, context_manager=context_manager)),
        ("goals_agent", build_goals(llm=worker_llm, checkpointer=checkpointer, user_id=user_id, context_manager=context_manager)),
        ("document_agent", build_document(llm=worker_llm, checkpointer=checkpointer, user_id=user_id, context_manager=context_manager)),
        ("connectors_agent", build_connectors(llm=worker_llm, checkpointer=checkpointer, user_id=user_id, context_manager=context_manager, connected_tool_ids=connected_tool_ids)),
    ]

    # langgraph_supervisor requires each agent to carry a .name attribute for routing.
    # CompiledStateGraph exposes a mutable .name attribute — set it directly.
    workers = []
    for name, agent in agent_specs:
        try:
            agent.name = name  # type: ignore[attr-defined]
        except Exception:
            pass
        workers.append(agent)

    # Use create_supervisor if available, otherwise fall back to a react agent that acts as supervisor
    try:
        from langgraph_supervisor import create_supervisor
        # create_supervisor returns a StateGraph; .compile() gives us a CompiledStateGraph
        return create_supervisor(
            agents=workers,
            model=routing_llm,
            prompt=SUPERVISOR_SYSTEM_PROMPT,
        ).compile(checkpointer=checkpointer)
    except (ImportError, AttributeError, TypeError) as e:
        logger.warning(f"langgraph_supervisor.create_supervisor unavailable ({e}), using react agent fallback")
        from langgraph.prebuilt import create_react_agent
        return create_react_agent(
            model=routing_llm,
            tools=[],
            prompt=SUPERVISOR_SYSTEM_PROMPT,
            checkpointer=checkpointer,
        )
