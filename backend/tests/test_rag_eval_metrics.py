import pytest

pytest.importorskip(
    "deepeval",
    reason="DeepEval is installed only with requirements-evals.txt",
)

from deepeval.test_case import LLMTestCase

from tests.evals.metrics import (
    ExpectedDocumentHitMetric,
    ExpectedDocumentPrecisionMetric,
    ExpectedDocumentReciprocalRankMetric,
    ExpectedContextHitMetric,
    ExpectedContextPrecisionMetric,
    ExpectedContextReciprocalRankMetric,
)


def make_case(retrieved):
    return LLMTestCase(
        input="query",
        actual_output="answer",
        context=["alpha source text beta source text"],
        retrieval_context=retrieved,
        metadata={
            "expected_document_id": "doc-b",
            "retrieved_document_ids": ["doc-a", "doc-b", "doc-b"],
        },
    )


def test_expected_context_metrics_score_ranked_exact_source_chunks():
    case = make_case(["unrelated", "alpha source text", "beta source text"])

    precision = ExpectedContextPrecisionMetric(0.5)
    hit = ExpectedContextHitMetric(1.0)
    reciprocal_rank = ExpectedContextReciprocalRankMetric(0.5)

    assert precision.measure(case) == (1 / 2 + 2 / 3) / 2
    assert hit.measure(case) == 1.0
    assert reciprocal_rank.measure(case) == 0.5


def test_expected_context_metrics_score_a_total_miss():
    case = make_case(["unrelated"])

    assert ExpectedContextPrecisionMetric(0.5).measure(case) == 0.0
    assert ExpectedContextHitMetric(1.0).measure(case) == 0.0
    assert ExpectedContextReciprocalRankMetric(0.5).measure(case) == 0.0


def test_expected_document_metrics_use_stable_document_identity():
    case = make_case(["adjacent source chunk", "another adjacent chunk"])

    precision = ExpectedDocumentPrecisionMetric(0.5)
    hit = ExpectedDocumentHitMetric(1.0)
    reciprocal_rank = ExpectedDocumentReciprocalRankMetric(0.5)

    assert precision.measure(case) == 0.5
    assert hit.measure(case) == 1.0
    assert reciprocal_rank.measure(case) == 0.5
