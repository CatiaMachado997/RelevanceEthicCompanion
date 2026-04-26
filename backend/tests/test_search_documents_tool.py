"""Tests for SearchDocumentsTool — the LangChain wrapper around RagRetrievalService."""

import pytest
from unittest.mock import AsyncMock, MagicMock


USER_ID = "00000000-0000-0000-0000-000000000000"


def _make_retrieval_mock(results):
    svc = MagicMock()
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
