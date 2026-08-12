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
