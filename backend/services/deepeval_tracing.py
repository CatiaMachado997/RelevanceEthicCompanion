"""Optional DeepEval + LangSmith instrumentation with safe defaults.

Tracing activates only when ``DEEPEVAL_TRACING_ENABLED=1`` and DeepEval is
installed. This keeps normal application startup unchanged while allowing the
local evaluation harness to capture real retriever spans.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def observe_retriever(function: F) -> F:
    wrapped: F = function
    if os.getenv("LANGSMITH_TRACING", "").lower() == "true" and os.getenv(
        "LANGSMITH_API_KEY"
    ):
        try:
            from langsmith import traceable

            wrapped = traceable(run_type="retriever", name="ethic-companion-rag")(
                wrapped
            )  # type: ignore[assignment]
        except ImportError:
            pass
    if os.getenv("DEEPEVAL_TRACING_ENABLED") == "1":
        try:
            from deepeval.tracing import observe

            wrapped = observe(type="retriever")(wrapped)  # type: ignore[assignment]
        except ImportError:
            pass
    return wrapped


def observe_chatbot(function: F) -> F:
    """Optionally make a full chatbot turn the root DeepEval/LangSmith span."""
    wrapped: F = function
    if os.getenv("LANGSMITH_TRACING", "").lower() == "true" and os.getenv(
        "LANGSMITH_API_KEY"
    ):
        try:
            from langsmith import traceable

            wrapped = traceable(run_type="chain", name="ethic-companion-chat")(wrapped)  # type: ignore[assignment]
        except ImportError:
            pass
    if os.getenv("DEEPEVAL_TRACING_ENABLED") == "1":
        try:
            from deepeval.tracing import observe

            wrapped = observe(type="agent")(wrapped)  # type: ignore[assignment]
        except ImportError:
            pass
    return wrapped


def update_retriever_span(
    *, query: str, results: list[dict[str, Any]], metadata: dict[str, Any]
) -> None:
    if os.getenv("DEEPEVAL_TRACING_ENABLED") != "1":
        return
    try:
        from deepeval.tracing import update_current_span
    except ImportError:
        return
    update_current_span(
        input=query,
        output=results,
        retrieval_context=[str(row.get("snippet") or "") for row in results],
        metadata=metadata,
        integration="ethic-companion-rag",
    )


def update_chatbot_span(
    *, prompt: str, answer: str, retrieval_context: list[str], metadata: dict[str, Any]
) -> None:
    if os.getenv("DEEPEVAL_TRACING_ENABLED") != "1":
        return
    try:
        from deepeval.tracing import update_current_span, update_current_trace
    except ImportError:
        return
    values = {
        "input": prompt,
        "output": answer,
        "retrieval_context": retrieval_context,
        "metadata": metadata,
    }
    update_current_span(
        input=prompt,
        output=answer,
        retrieval_context=retrieval_context,
        metadata=metadata,
        integration="ethic-companion-chat",
    )
    # Golden assertions evaluate the root trace test case. Populate that trace
    # explicitly as well as the agent span so trace-level metrics receive RAG
    # context instead of seeing a missing field.
    update_current_trace(**values)


def assert_grounded_turn_contract(result: dict[str, Any]) -> None:
    """Validate that a forced-retrieval eval kept evidence and citations linked."""
    answer = str(result.get("answer") or "").strip()
    assert answer, "The application returned an empty answer"

    done = result.get("done") or {}
    sources = done.get("document_sources") or []
    retrieval_context = result.get("retrieval_context") or []
    assert sources, "Forced retrieval returned no structured document sources"
    assert retrieval_context, "Forced retrieval returned no context for evaluation"
    assert len(retrieval_context) == len(sources), (
        "Trace retrieval context and structured document sources diverged: "
        f"{len(retrieval_context)} contexts != {len(sources)} sources"
    )

    citation_tools = {
        str(citation.get("tool") or "")
        for citation in (done.get("citations") or [])
        if isinstance(citation, dict)
    }
    assert (
        "search_documents" in citation_tools
    ), "Retrieved document evidence was not represented in structured citations"


@observe_chatbot
async def run_traced_chatbot_turn(
    *,
    user_id: str,
    message: str,
    model: str,
    conversation_id: str | None = None,
    force_retrieval: bool = True,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Consume the real stream entrypoint and return an eval-friendly turn."""
    from orchestrator.graph import stream_langgraph

    answer_parts: list[str] = []
    done: dict[str, Any] = {}
    tool_events: list[dict[str, Any]] = []
    async for event in stream_langgraph(
        user_id=user_id,
        message=message,
        model=model,
        conversation_id=conversation_id,
        force_retrieval=force_retrieval,
        persist_turn=False,
        conversation_history_override=conversation_history,
    ):
        if event.get("event") == "token":
            answer_parts.append(str(event.get("token") or ""))
        elif event.get("event") == "error":
            raise RuntimeError(str(event.get("message") or "Chat evaluation failed"))
        elif event.get("event") == "done":
            done = event
        elif event.get("event") in {
            "tool_use",
            "tool_result",
            "tool_error",
            "tool_cancelled",
            "tool_skipped",
            "plan_paused",
        }:
            # Trace only operational outcomes and identifiers; never copy raw
            # tool inputs or provider responses into hosted metadata.
            tool_events.append(
                {
                    key: event.get(key)
                    for key in (
                        "event",
                        "tool",
                        "step",
                        "action_index",
                        "status",
                        "error_code",
                        "retryable",
                    )
                    if event.get(key) is not None
                }
            )

    answer = "".join(answer_parts)
    sources = done.get("document_sources") or []
    retrieval_context = [
        str(source.get("snippet") or source.get("content") or "")
        for source in sources
        if isinstance(source, dict)
    ]
    update_chatbot_span(
        prompt=message,
        answer=answer,
        retrieval_context=retrieval_context,
        metadata={
            "model": model,
            "conversation_id": conversation_id,
            "citations": done.get("citations") or [],
            "citation_tools": [
                str(citation.get("tool") or "")
                for citation in (done.get("citations") or [])
                if isinstance(citation, dict)
            ],
            "retrieved_sources": [
                str(source.get("filename") or source.get("source_type") or "")
                for source in sources
                if isinstance(source, dict)
            ],
            "retrieval_count": len(retrieval_context),
            "assistant_turn_id": done.get("assistant_turn_id"),
            "tool_events": tool_events,
            "tool_error_count": sum(
                event.get("event") == "tool_error" for event in tool_events
            ),
            "paused_action_count": sum(
                event.get("event") == "plan_paused" for event in tool_events
            ),
        },
    )
    return {
        "answer": answer,
        "retrieval_context": retrieval_context,
        "done": done,
        "tool_events": tool_events,
    }
