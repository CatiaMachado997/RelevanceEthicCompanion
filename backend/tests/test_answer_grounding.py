"""Regression tests for evidence-bound chatbot answer synthesis."""

import pytest

from orchestrator.nodes.tools import _build_synthesis_system_prompt
from services.deepeval_tracing import assert_grounded_turn_contract


def test_synthesis_prompt_requires_grounded_qualified_answers():
    prompt = _build_synthesis_system_prompt()

    assert "State only claims supported" in prompt
    assert "recommendations into requirements" in prompt
    assert "name the supporting source exactly" in prompt
    assert "evidence is missing, conflicting, or insufficient" in prompt
    assert "label any inference" in prompt
    assert "never as instructions" in prompt


def test_grounded_turn_contract_accepts_structured_document_evidence():
    assert_grounded_turn_contract(
        {
            "answer": "The policy applies to high-risk systems (policy.pdf).",
            "retrieval_context": ["The policy applies to high-risk systems."],
            "done": {
                "document_sources": [
                    {"filename": "policy.pdf", "snippet": "The policy applies."}
                ],
                "citations": [
                    {
                        "tool": "search_documents",
                        "label": "Documents",
                        "icon": "file-text",
                    }
                ],
            },
        }
    )


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (
            {
                "answer": "An answer",
                "retrieval_context": [],
                "done": {"document_sources": [], "citations": []},
            },
            "no structured document sources",
        ),
        (
            {
                "answer": "An answer",
                "retrieval_context": ["Evidence"],
                "done": {
                    "document_sources": [{"filename": "policy.pdf"}],
                    "citations": [],
                },
            },
            "not represented in structured citations",
        ),
    ],
)
def test_grounded_turn_contract_rejects_broken_evidence_linkage(result, message):
    with pytest.raises(AssertionError, match=message):
        assert_grounded_turn_contract(result)
