import importlib
from unittest.mock import patch

import pytest


def test_tracing_is_noop_by_default(monkeypatch):
    monkeypatch.delenv("DEEPEVAL_TRACING_ENABLED", raising=False)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    module = importlib.import_module("services.deepeval_tracing")

    def retrieve():
        return "ok"

    assert module.observe_retriever(retrieve) is retrieve


def test_langsmith_requires_api_key(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    module = importlib.import_module("services.deepeval_tracing")

    def retrieve():
        return "ok"

    assert module.observe_retriever(retrieve) is retrieve


@pytest.mark.asyncio
async def test_chat_trace_records_safe_tool_outcomes(monkeypatch):
    monkeypatch.setenv("DEEPEVAL_TRACING_ENABLED", "1")
    module = importlib.import_module("services.deepeval_tracing")

    async def fake_stream(**kwargs):
        yield {"event": "tool_use", "tool": "send_email", "params": {"secret": "x"}}
        yield {
            "event": "tool_error",
            "tool": "send_email",
            "error_code": "action_outcome_uncertain",
            "retryable": False,
            "message": "private provider detail",
        }
        yield {"event": "token", "token": "I could not confirm the outcome."}
        yield {"event": "done", "citations": [], "document_sources": []}

    captured = {}
    with patch("orchestrator.graph.stream_langgraph", fake_stream), patch.object(
        module,
        "update_chatbot_span",
        side_effect=lambda **kwargs: captured.update(kwargs),
    ):
        result = await module.run_traced_chatbot_turn(
            user_id="user-1", message="send it", model="model"
        )

    assert result["tool_events"][1]["error_code"] == "action_outcome_uncertain"
    metadata = captured["metadata"]
    assert metadata["tool_error_count"] == 1
    serialized = str(metadata)
    assert "secret" not in serialized
    assert "private provider detail" not in serialized
