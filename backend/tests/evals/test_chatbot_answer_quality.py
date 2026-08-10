"""DeepEval answer-level suite over the real streaming chatbot entrypoint."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import pytest
from deepeval import assert_test, log_hyperparameters
from deepeval.dataset import Golden

from config import settings
from services.deepeval_tracing import run_traced_chatbot_turn
from tests.evals.metrics import chatbot_answer_metrics

SHARD_DIR = Path(
    os.getenv(
        "RAG_EVAL_DATA_DIR",
        str(Path(__file__).resolve().parent / "synthetic_data"),
    )
)
SHARD_PATTERN = re.compile(r"rag_(\d+)_(\d+)\.json")


def load_cases() -> list[dict]:
    cases: list[dict] = []
    for path in sorted(SHARD_DIR.glob("rag_[0-9]*_[0-9]*.json")):
        if SHARD_PATTERN.fullmatch(path.name):
            cases.extend(json.loads(path.read_text(encoding="utf-8")))
    limit = int(os.getenv("CHATBOT_EVAL_LIMIT", "20"))
    return cases[:limit]


CASES = load_cases()


@log_hyperparameters
def chatbot_eval_hyperparameters():
    return {
        "app_model": os.getenv("CHATBOT_EVAL_APP_MODEL", "llama-3.3-70b-versatile"),
        "judge_model": os.getenv("GROQ_EVAL_MODEL", "openai/gpt-oss-20b"),
        "force_retrieval": True,
        "rag_rollout_variant": os.getenv("RAG_ROLLOUT_FORCE_VARIANT", "assigned"),
    }


@pytest.mark.integration
@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[f"chat-answer-{index:03d}" for index in range(len(CASES))],
)
def test_chatbot_answer_quality(case: dict):
    result = asyncio.run(
        run_traced_chatbot_turn(
            user_id=settings.DEV_USER_ID,
            message=case["scenario"],
            model=os.getenv("CHATBOT_EVAL_APP_MODEL", "llama-3.3-70b-versatile"),
        )
    )
    assert result["answer"], "The application returned an empty answer"
    golden = Golden(
        input=case["scenario"],
        expected_output=case.get("expected_outcome"),
        context=case.get("context"),
    )
    assert_test(golden=golden, metrics=chatbot_answer_metrics())
