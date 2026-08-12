"""Stable, quota-independent DeepEval metrics for RAG retrieval."""

from __future__ import annotations

import os

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase, SingleTurnParams


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _relevance_flags(test_case: LLMTestCase) -> list[bool]:
    expected = [_normalize(value) for value in (test_case.context or [])]
    return [
        any(_normalize(chunk) in source for source in expected)
        for chunk in (test_case.retrieval_context or [])
    ]


def _document_relevance_flags(test_case: LLMTestCase) -> list[bool]:
    metadata = test_case.metadata or {}
    expected = str(metadata.get("expected_document_id") or "")
    retrieved = metadata.get("retrieved_document_ids") or []
    found = False
    flags: list[bool] = []
    for document_id in retrieved:
        relevant = bool(expected) and str(document_id) == expected and not found
        flags.append(relevant)
        found = found or relevant
    return flags


def _source_relevance_flags(test_case: LLMTestCase) -> list[bool]:
    metadata = test_case.metadata or {}
    expected = str(metadata.get("expected_source_name") or "").casefold()
    retrieved = metadata.get("retrieved_filenames") or []
    found = False
    flags: list[bool] = []
    for filename in retrieved:
        normalized = str(filename or "").rsplit("/", 1)[-1].casefold()
        relevant = bool(expected) and normalized == expected and not found
        flags.append(relevant)
        found = found or relevant
    return flags


class _ExpectedContextMetric(BaseMetric):
    _required_params = [SingleTurnParams.CONTEXT, SingleTurnParams.RETRIEVAL_CONTEXT]
    async_mode = False
    include_reason = True
    evaluation_model = "deterministic-expected-context"

    def __init__(self, threshold: float):
        self.threshold = threshold

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case, *args, **kwargs)


class ExpectedContextPrecisionMetric(_ExpectedContextMetric):
    """Average precision of source chunks, independent of how many chunks exist."""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        flags = _relevance_flags(test_case)
        precisions = [
            sum(flags[: index + 1]) / (index + 1)
            for index, relevant in enumerate(flags)
            if relevant
        ]
        self.score = sum(precisions) / len(precisions) if precisions else 0.0
        ranks = [index + 1 for index, relevant in enumerate(flags) if relevant]
        self.reason = f"source matches at ranks {ranks}" if ranks else "source missed"
        self.success = self.is_successful()
        return self.score

    @property
    def __name__(self) -> str:
        return "Expected Context Average Precision"


class ExpectedContextHitMetric(_ExpectedContextMetric):
    """Whether at least one top-k chunk comes from the golden source context."""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        flags = _relevance_flags(test_case)
        self.score = 1.0 if any(flags) else 0.0
        self.reason = (
            "source context retrieved" if self.score else "source context missed"
        )
        self.success = self.is_successful()
        return self.score

    @property
    def __name__(self) -> str:
        return "Expected Context Hit Rate"


class ExpectedContextReciprocalRankMetric(_ExpectedContextMetric):
    """Reciprocal rank of the first chunk from the golden source context."""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        flags = _relevance_flags(test_case)
        first_rank = next((index + 1 for index, flag in enumerate(flags) if flag), None)
        self.score = 1.0 / first_rank if first_rank else 0.0
        self.reason = (
            f"first source match at rank {first_rank}"
            if first_rank
            else "source context absent from top-k"
        )
        self.success = self.is_successful()
        return self.score

    @property
    def __name__(self) -> str:
        return "Expected Context Reciprocal Rank"


class _ExpectedDocumentMetric(_ExpectedContextMetric):
    """Base class for strict synthetic context-container identity metrics."""


class ExpectedDocumentPrecisionMetric(_ExpectedDocumentMetric):
    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        flags = _document_relevance_flags(test_case)
        precisions = [
            sum(flags[: index + 1]) / (index + 1)
            for index, relevant in enumerate(flags)
            if relevant
        ]
        self.score = sum(precisions) / len(precisions) if precisions else 0.0
        ranks = [index + 1 for index, relevant in enumerate(flags) if relevant]
        self.reason = (
            f"expected document matches at ranks {ranks}"
            if ranks
            else "expected document missed"
        )
        self.success = self.is_successful()
        return self.score

    @property
    def __name__(self) -> str:
        return "Expected Document Average Precision"


class ExpectedDocumentHitMetric(_ExpectedDocumentMetric):
    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        self.score = 1.0 if any(_document_relevance_flags(test_case)) else 0.0
        self.reason = (
            "expected document retrieved" if self.score else "expected document missed"
        )
        self.success = self.is_successful()
        return self.score

    @property
    def __name__(self) -> str:
        return "Expected Document Hit Rate"


class ExpectedDocumentReciprocalRankMetric(_ExpectedDocumentMetric):
    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        flags = _document_relevance_flags(test_case)
        first_rank = next((index + 1 for index, flag in enumerate(flags) if flag), None)
        self.score = 1.0 / first_rank if first_rank else 0.0
        self.reason = (
            f"expected document first appears at rank {first_rank}"
            if first_rank
            else "expected document absent"
        )
        self.success = self.is_successful()
        return self.score

    @property
    def __name__(self) -> str:
        return "Expected Document Reciprocal Rank"


class ExpectedSourcePrecisionMetric(_ExpectedContextMetric):
    """Average precision using the authoritative source filename identity."""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        flags = _source_relevance_flags(test_case)
        precisions = [
            sum(flags[: index + 1]) / (index + 1)
            for index, relevant in enumerate(flags)
            if relevant
        ]
        self.score = sum(precisions) / len(precisions) if precisions else 0.0
        ranks = [index + 1 for index, relevant in enumerate(flags) if relevant]
        self.reason = (
            f"expected source matches at ranks {ranks}"
            if ranks
            else "expected source missed"
        )
        self.success = self.is_successful()
        return self.score

    @property
    def __name__(self) -> str:
        return "Expected Source Average Precision"


class ExpectedSourceHitMetric(_ExpectedContextMetric):
    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        self.score = 1.0 if any(_source_relevance_flags(test_case)) else 0.0
        self.reason = (
            "expected source retrieved" if self.score else "expected source missed"
        )
        self.success = self.is_successful()
        return self.score

    @property
    def __name__(self) -> str:
        return "Expected Source Hit Rate"


class ExpectedSourceReciprocalRankMetric(_ExpectedContextMetric):
    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        flags = _source_relevance_flags(test_case)
        first_rank = next((index + 1 for index, flag in enumerate(flags) if flag), None)
        self.score = 1.0 / first_rank if first_rank else 0.0
        self.reason = (
            f"expected source first appears at rank {first_rank}"
            if first_rank
            else "expected source absent"
        )
        self.success = self.is_successful()
        return self.score

    @property
    def __name__(self) -> str:
        return "Expected Source Reciprocal Rank"


RAG_RETRIEVER_METRICS = [
    ExpectedSourcePrecisionMetric(threshold=0.6),
    ExpectedSourceHitMetric(threshold=1.0),
    ExpectedSourceReciprocalRankMetric(threshold=0.5),
]

RAG_STRICT_DOCUMENT_ID_METRICS = [
    ExpectedDocumentPrecisionMetric(threshold=0.6),
    ExpectedDocumentHitMetric(threshold=1.0),
    ExpectedDocumentReciprocalRankMetric(threshold=0.5),
]

RAG_STRICT_CHUNK_METRICS = [
    ExpectedContextPrecisionMetric(threshold=0.6),
    ExpectedContextHitMetric(threshold=1.0),
    ExpectedContextReciprocalRankMetric(threshold=0.5),
]


def chatbot_answer_metrics():
    """Create judge-backed metrics after the selected eval provider is configured."""
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
        GEval,
    )
    from deepeval.test_case import LLMTestCaseParams

    async_mode = os.getenv("DEEPEVAL_METRICS_ASYNC", "0") == "1"
    return [
        FaithfulnessMetric(threshold=0.7, async_mode=async_mode),
        AnswerRelevancyMetric(threshold=0.7, async_mode=async_mode),
        GEval(
            name="Grounded answer correctness",
            criteria=(
                "The answer must correctly address the request, preserve important "
                "qualifications from the expected answer, and avoid unsupported claims."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.RETRIEVAL_CONTEXT,
            ],
            threshold=0.7,
            async_mode=async_mode,
        ),
    ]


def chatbot_conversation_metrics():
    """Metrics that evaluate behavior across turns, not isolated answers."""
    from deepeval.metrics import (
        ConversationCompletenessMetric,
        KnowledgeRetentionMetric,
        RoleAdherenceMetric,
        TurnRelevancyMetric,
    )

    async_mode = os.getenv("DEEPEVAL_METRICS_ASYNC", "0") == "1"
    return [
        ConversationCompletenessMetric(threshold=0.7, async_mode=async_mode),
        KnowledgeRetentionMetric(threshold=0.7, async_mode=async_mode),
        TurnRelevancyMetric(threshold=0.7, async_mode=async_mode),
        RoleAdherenceMetric(threshold=0.7, async_mode=async_mode),
    ]
