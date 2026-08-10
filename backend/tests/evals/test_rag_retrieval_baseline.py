"""DeepEval baseline over the real Ollama + Weaviate retriever."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path

import pytest
from deepeval import assert_test, log_hyperparameters
from deepeval.test_case import LLMTestCase

from config import settings
from services.rag_retrieval import RagRetrievalService
from tests.evals.metrics import RAG_RETRIEVER_METRICS

EVAL_DIR = Path(__file__).resolve().parent
SHARD_DIR = Path(os.getenv("RAG_EVAL_DATA_DIR", str(EVAL_DIR / "synthetic_data")))
MANIFEST_PATH = Path(
    os.getenv(
        "RAG_EVAL_MANIFEST",
        str(SHARD_DIR.parent / "contexts.manifest.json"),
    )
)
SHARD_PATTERN = re.compile(r"rag_(\d+)_(\d+)\.json")


def load_generated_scenarios() -> list[dict]:
    """Read canonical shards directly so the suite creates no dataset copy."""
    rows: list[dict] = []
    shards = sorted(SHARD_DIR.glob("rag_[0-9]*_[0-9]*.json"))
    if not shards:
        return rows
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_contexts = manifest.get("contexts") or []
    for shard in shards:
        match = SHARD_PATTERN.fullmatch(shard.name)
        if match is None:
            continue
        start, end = (int(value) for value in match.groups())
        shard_rows = json.loads(shard.read_text(encoding="utf-8"))
        expected_rows = (end - start + 1) * 2
        if len(shard_rows) != expected_rows:
            raise ValueError(
                f"{shard} has {len(shard_rows)} rows; expected {expected_rows}"
            )
        for offset, row in enumerate(shard_rows):
            context_index = start + offset // 2
            if context_index >= len(source_contexts):
                raise ValueError(
                    f"No source manifest entry for context {context_index}"
                )
            rows.append(
                {
                    **row,
                    "_context_index": context_index,
                    "_expected_source_name": source_contexts[context_index][
                        "source_name"
                    ],
                }
            )
    limit = int(os.getenv("RAG_EVAL_LIMIT", str(len(rows))))
    return rows[:limit]


CASES = load_generated_scenarios()
TOP_K = int(os.getenv("RAG_EVAL_TOP_K", "5"))


@log_hyperparameters
def rag_eval_hyperparameters():
    return {
        "embedding_model": settings.OLLAMA_EMBEDDING_MODEL,
        "hybrid_alpha": float(os.getenv("RAG_HYBRID_ALPHA", "0.5")),
        "top_k": TOP_K,
        "candidate_floor": int(os.getenv("RAG_CANDIDATE_FLOOR", "20")),
        "query_expansion": os.getenv("RAG_QUERY_EXPANSION", "0") == "1",
        "rerank_provider": settings.RAG_RERANK_PROVIDER,
        "local_rerank_lexical_weight": float(
            os.getenv("RAG_LOCAL_RERANK_LEXICAL_WEIGHT", "0.2")
        ),
    }


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
            "expected_source_name": golden["_expected_source_name"],
            "retrieved_filenames": [row.get("filename") for row in results],
            "retrieved_chunk_uuids": [row.get("chunk_uuid") for row in results],
        },
    )
    assert_test(test_case=test_case, metrics=RAG_RETRIEVER_METRICS)
