"""Tests for SearchDocumentsTool — the LangChain wrapper around RagRetrievalService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


USER_ID = "00000000-0000-0000-0000-000000000000"


def _make_retrieval_mock(results):
    # Use spec so the tool's hasattr() probe for `retrieve_with_trace` (Sprint G
    # Task 4) returns False — this fixture covers the legacy retrieve-only path.
    svc = MagicMock(spec=["retrieve"])
    svc.retrieve = AsyncMock(return_value=results)
    return svc


@pytest.mark.asyncio
async def test_returns_no_match_message_when_empty():
    from services.langchain_tools import SearchDocumentsTool

    collector: list = []
    tool = SearchDocumentsTool(
        retrieval_service=_make_retrieval_mock([]),
        user_id=USER_ID,
        citation_collector=collector,
    )

    out = await tool._arun("anything")
    assert "No matching" in out
    assert collector == []


@pytest.mark.asyncio
async def test_appends_citations_to_collector():
    from services.langchain_tools import SearchDocumentsTool

    rows = [
        {
            "chunk_uuid": "u1",
            "document_id": "d1",
            "filename": "brief.md",
            "chunk_index": 0,
            "snippet": "Quarterly results were strong.",
            "score": 0.88,
        },
        {
            "chunk_uuid": "u2",
            "document_id": "d1",
            "filename": "brief.md",
            "chunk_index": 1,
            "snippet": "Revenue grew 12%.",
            "score": 0.81,
        },
    ]
    collector: list = []
    tool = SearchDocumentsTool(
        retrieval_service=_make_retrieval_mock(rows),
        user_id=USER_ID,
        citation_collector=collector,
    )

    out = await tool._arun("how were quarterly results?")

    assert "Found 2 relevant excerpts" in out
    assert "brief.md" in out
    assert collector == rows


@pytest.mark.asyncio
async def test_dedupes_citations_across_calls():
    """Repeated retrieval of the same chunk only adds it once to the collector."""
    from services.langchain_tools import SearchDocumentsTool

    row = {
        "chunk_uuid": "u1",
        "document_id": "d1",
        "filename": "x.md",
        "chunk_index": 0,
        "snippet": "hi",
        "score": 0.5,
    }
    collector: list = []
    tool = SearchDocumentsTool(
        retrieval_service=_make_retrieval_mock([row]),
        user_id=USER_ID,
        citation_collector=collector,
    )

    await tool._arun("first")
    await tool._arun("second")

    assert len(collector) == 1


@pytest.mark.asyncio
async def test_tool_stashes_trace_from_retrieve_with_trace():
    """Sprint G Task 4: when the retrieval service exposes
    `retrieve_with_trace`, the tool calls it and stashes the trace on
    `last_trace` for the orchestrator to fold into telemetry output."""
    from services.langchain_tools import SearchDocumentsTool

    rows = [
        {
            "chunk_uuid": "u1",
            "filename": "x.md",
            "snippet": "hi",
            "score": 0.5,
        }
    ]
    trace = {
        "query": "q",
        "candidates": [
            {"chunk_uuid": "u1", "hybrid_score": 0.5, "snippet_preview": "hi"}
        ],
        "rerank_applied": False,
        "rerank_top": None,
        "final": ["u1"],
    }
    svc = MagicMock()
    svc.retrieve_with_trace = AsyncMock(return_value=(rows, trace))

    collector: list = []
    tool = SearchDocumentsTool(
        retrieval_service=svc, user_id=USER_ID, citation_collector=collector
    )

    out = await tool._arun("q")
    assert "Found 1 relevant excerpts" in out
    assert tool.last_trace == trace
    svc.retrieve_with_trace.assert_awaited_once()


@pytest.mark.asyncio
async def test_trace_is_recorded_into_tool_call_events_output():
    """Sprint G Task 4: the orchestrator's tool-execution path must fold the
    `search_documents` retrieval trace into the `tool_call_events.output`
    JSONB so the Transparency UI can render the breadcrumbs."""
    from orchestrator.nodes.tools import tool_execution_node

    rows = [
        {
            "chunk_uuid": "u1",
            "filename": "brief.md",
            "snippet": "Project Atlas is the top initiative.",
            "score": 0.88,
        }
    ]
    expected_trace = {
        "query": "what is project atlas?",
        "candidates": [
            {
                "chunk_uuid": "u1",
                "hybrid_score": 0.88,
                "snippet_preview": "Project Atlas is the top initiative.",
            }
        ],
        "rerank_applied": False,
        "rerank_top": None,
        "final": ["u1"],
    }

    fake_retrieval = MagicMock()
    fake_retrieval.retrieve_with_trace = AsyncMock(
        return_value=(rows, expected_trace)
    )

    from services.langchain_tools import SearchDocumentsTool

    sd_tool = SearchDocumentsTool(
        retrieval_service=fake_retrieval,
        user_id=USER_ID,
        citation_collector=[],
    )

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content="ok"))

    state = {
        "user_id": USER_ID,
        "message": "what is project atlas?",
        "conversation_id": "conv-1",
        "model": "llama-3.3-70b-versatile",
        "tool_calls": [
            {
                "name": "search_documents",
                "args": {"query": "what is project atlas?", "k": 5},
                "id": "call_1",
            }
        ],
        "tool_results": [],
        "active_sources": [],
        "document_sources": [],
        "proposed_content": "",
    }

    captured: dict = {}

    def fake_record(**kwargs):
        captured.update(kwargs)
        return "evt-1"

    telemetry_inst = MagicMock()
    telemetry_inst.record_tool_call = MagicMock(side_effect=fake_record)

    with patch(
        "orchestrator.nodes.tools.get_context_manager", return_value=MagicMock()
    ), patch(
        "services.langchain_tools.create_langchain_tools",
        AsyncMock(return_value=[sd_tool]),
    ), patch(
        "langchain_groq.ChatGroq", return_value=fake_llm
    ), patch(
        "services.tool_telemetry.ToolTelemetryService", return_value=telemetry_inst
    ):
        await tool_execution_node(state)

    assert captured.get("tool_name") == "search_documents"
    assert captured.get("status") == "success"
    output = captured.get("output")
    assert isinstance(output, dict), f"expected dict output, got {type(output)}"
    assert "trace" in output
    assert output["trace"] == expected_trace
    assert "result" in output


@pytest.mark.asyncio
async def test_factory_always_registers_search_documents():
    """search_documents tool is always registered so the planner sees its schema."""
    from services.langchain_tools import create_langchain_tools

    cm = MagicMock()
    tools = await create_langchain_tools(cm, USER_ID)
    names = {t.name for t in tools}
    assert "search_documents" in names

    # When a collector is provided, it's the same list the tool will append to.
    collector: list = []
    tools_with = await create_langchain_tools(cm, USER_ID, citation_collector=collector)
    sd = next(t for t in tools_with if t.name == "search_documents")
    assert sd.citation_collector is collector
