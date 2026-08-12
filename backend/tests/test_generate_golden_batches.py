import json

import pytest

from scripts.generate_golden_batches import (
    audit_shard_grounding,
    inspect_shards,
    missing_batches,
    validate_grounding,
)


def _write_shard(path, count):
    path.write_text(json.dumps([{"input": str(i)} for i in range(count)]))


def test_missing_batches_respects_coverage_from_different_shard_sizes(tmp_path):
    _write_shard(tmp_path / "rag_000_004.json", 10)
    _write_shard(tmp_path / "rag_005_009.json", 10)

    covered, row_count = inspect_shards(tmp_path, context_count=15)

    assert covered == set(range(10))
    assert row_count == 20
    assert missing_batches(15, covered, batch_size=1) == [
        [10],
        [11],
        [12],
        [13],
        [14],
    ]


def test_inspect_shards_rejects_overlapping_ranges(tmp_path):
    _write_shard(tmp_path / "rag_000_004.json", 10)
    _write_shard(tmp_path / "rag_004_005.json", 4)

    with pytest.raises(ValueError, match="Overlapping shard"):
        inspect_shards(tmp_path, context_count=10)


def test_inspect_shards_rejects_incomplete_shard(tmp_path):
    _write_shard(tmp_path / "rag_000_004.json", 9)

    with pytest.raises(ValueError, match="expected 10"):
        inspect_shards(tmp_path, context_count=10)


def test_validate_grounding_accepts_source_anchored_case():
    validate_grounding(
        [
            {
                "scenario": "An organization evaluates generative AI risk management.",
                "expected_outcome": "Apply the AI RMF governance and risk framework.",
                "context": [
                    "Organizations use the AI RMF framework to govern generative AI "
                    "and manage risk."
                ],
            }
        ]
    )


def test_validate_grounding_rejects_unrelated_case():
    with pytest.raises(ValueError, match="not grounded"):
        validate_grounding(
            [
                {
                    "scenario": "Colleagues compare Einstein's Nobel Prize year.",
                    "expected_outcome": "Explain the award's impact on physics.",
                    "context": ["The NIST AI RMF manages generative AI risks."],
                }
            ]
        )


def test_validate_grounding_rejects_prompt_leakage():
    with pytest.raises(ValueError, match="leaked generation instructions"):
        validate_grounding(
            [
                {
                    "scenario": (
                        "Here is a rewritten scenario preserving factual correctness: "
                        "an organization manages generative AI risk."
                    ),
                    "expected_outcome": "Apply the AI RMF risk framework.",
                    "context": [
                        "Organizations apply the AI RMF framework to manage "
                        "generative AI risk."
                    ],
                }
            ]
        )


def test_validate_grounding_uses_semantic_fallback_for_translation():
    calls = []

    def similarity(left, right):
        calls.append((left, right))
        return 0.8

    validate_grounding(
        [
            {
                "scenario": "A regulator reviews trustworthy artificial intelligence.",
                "expected_outcome": "The review results in a compliant system.",
                "context": [
                    "A União promove sistemas de IA de confiança e conformidade."
                ],
            }
        ],
        semantic_similarity=similarity,
    )

    assert calls


def test_audit_shard_grounding_reports_all_bad_shards(tmp_path):
    bad_row = {
        "scenario": "Here is a rewritten scenario about unrelated physics.",
        "expected_outcome": "Explain an award.",
        "context": ["Organizations apply an AI risk framework."],
    }
    (tmp_path / "rag_000_000.json").write_text(json.dumps([bad_row]))
    (tmp_path / "rag_001_001.json").write_text(json.dumps([bad_row]))

    failures = audit_shard_grounding(tmp_path)

    assert [path.name for path, _ in failures] == [
        "rag_000_000.json",
        "rag_001_001.json",
    ]
