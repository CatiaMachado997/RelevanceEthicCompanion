"""DeepEval-simulated multi-turn conversations over the real chatbot entrypoint."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from deepeval import assert_test, log_hyperparameters
from deepeval.dataset import EvaluationDataset
from deepeval.simulator import ConversationSimulator

from config import settings
from services.deepeval_tracing import run_traced_chatbot_turn
from tests.evals.metrics import chatbot_conversation_metrics


class ChatbotCallback:
    def __init__(self):
        self.history: list[dict[str, str]] = []

    def __call__(self, message: str) -> str:
        result = asyncio.run(
            asyncio.wait_for(
                run_traced_chatbot_turn(
                    user_id=settings.DEV_USER_ID,
                    message=message,
                    model=os.getenv(
                        "CHATBOT_EVAL_APP_MODEL", "llama-3.3-70b-versatile"
                    ),
                    conversation_history=self.history,
                ),
                timeout=float(os.getenv("CHATBOT_EVAL_TURN_TIMEOUT_SECONDS", "90")),
            )
        )
        answer = result["answer"]
        self.history.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": answer},
            ]
        )
        return answer


def simulate_cases() -> list:
    if os.getenv("RUN_CHATBOT_EVALS") != "1":
        return []
    dataset = EvaluationDataset()
    dataset.add_goldens_from_json_file(
        file_path=str(Path(__file__).with_name("chatbot_conversations.json"))
    )
    cases = []
    for golden in dataset.goldens:
        simulator = ConversationSimulator(
            model_callback=ChatbotCallback(), max_concurrent=1, async_mode=False
        )
        cases.extend(
            simulator.simulate(
                conversational_goldens=[golden],
                max_user_simulations=int(os.getenv("CHATBOT_EVAL_MAX_TURNS", "5")),
            )
        )
    return cases


CASES = simulate_cases()


@log_hyperparameters
def chatbot_multiturn_hyperparameters():
    return {
        "app_model": os.getenv("CHATBOT_EVAL_APP_MODEL", "llama-3.3-70b-versatile"),
        "judge_model": os.getenv("GROQ_EVAL_MODEL", "openai/gpt-oss-20b"),
        "metrics_async": os.getenv("DEEPEVAL_METRICS_ASYNC", "0") == "1",
        "max_turns": int(os.getenv("CHATBOT_EVAL_MAX_TURNS", "5")),
        "scenario_count": len(CASES),
    }


@pytest.mark.integration
@pytest.mark.parametrize("test_case", CASES)
def test_chatbot_multiturn_quality(test_case):
    assert_test(test_case=test_case, metrics=chatbot_conversation_metrics())
