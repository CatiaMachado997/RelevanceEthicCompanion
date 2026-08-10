"""DeepEval baseline over the real Ollama + Weaviate retriever."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from config import settings
from services.rag_retrieval import RagRetrievalService
from tests.evals.metrics import RAG_RETRIEVER_METRICS

EVAL_DIR = Path(__file__).resolve().parent
SHARD_DIR = Path(os.getenv("RAG_EVAL_DATA_DIR", str(EVAL_DIR / "synthetic_data")))
SHARD_PATTERN = re.compile(r"rag_(\d+)_(\d+)\.json")


def load_generated_scenarios() -> list[dict]:
    """Read canonical shards directly so the suite creates no dataset copy."""
    rows: list[dict] = []
    for shard in sorted(SHARD_DIR.glob("rag_[0-9]*_[0-9]*.json")):
        match = SHARD_PATTERN.fullmatch(shard.name)
        if match is None:
            continue
        start, end = (int(value) for value in match.groups())
        shard_rows = json.loads(shard.read_text(encoding="utf-8"))
        expected_rows = (end - start + 1) * 2
        if len(shard_rows) != expected_rows:
            raise ValueError(f"{shard} has {len(shard_rows)} rows; expected {expected_rows}")
        for offset, row in enumerate(shard_rows):
            context_index = start + offset // 2
            rows.append(
                {
                    **row,
                    "_context_index": context_index,
                    "_expected_document_id": f"eval-context-{context_index:03d}",
                }
            )
    limit = int(os.getenv("RAG_EVAL_LIMIT", str(len(rows))))
    return rows[:limit]


CASES = load_generated_scenarios()
TOP_K = int(os.getenv("RAG_EVAL_TOP_K", "5"))


@pytest.mark.integration
@pytest.mark.parametrize(
    "golden",
    CASES,
    ids=[f"rag-{index:03d}" for index in range(len(CASES))],
)
def test_rag_retrieval_baseline(golden: dict):
    delay = float(os.getenv("RAG_EVAL_DELAY_SECONDS", "0"))
    if delay:
        time.sleep(delay)
    service = RagRetrievalService()
    results, _trace = asyncio.run(
        service.retrieve_with_trace(
            golden["scenario"],
            settings.DEV_USER_ID,
            k=TOP_K,
        )
    )
    snippets = [row["snippet"] for row in results]
    test_case = LLMTestCase(
        input=golden["scenario"],
        actual_output="\n\n".join(snippets),
        retrieval_context=snippets,
        context=golden.get("context"),
        expected_output=golden.get("expected_outcome"),
        metadata={
            "context_index": golden["_context_index"],
            "expected_document_id": golden["_expected_document_id"],
            "retrieved_document_ids": [row.get("document_id") for row in results],
            "retrieved_chunk_uuids": [row.get("chunk_uuid") for row in results],
        },
    )
    assert_test(test_case=test_case, metrics=RAG_RETRIEVER_METRICS)
