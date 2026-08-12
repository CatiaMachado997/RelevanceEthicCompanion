from services.rag_query import (
    build_retrieval_queries,
    clean_retrieval_query,
    contextualize_followup_query,
    expand_multilingual_query,
    reciprocal_rank_fusion,
    retrieval_query_weights,
)


def test_contextualize_followup_query_uses_latest_user_turn():
    history = [
        {"role": "user", "content": "Compare the NIST and EU AI Act approaches."},
        {"role": "assistant", "content": "Here is the comparison."},
        {"role": "user", "content": "Use the NIST approach for the checklist."},
        {"role": "assistant", "content": "Drafted."},
    ]

    query = contextualize_followup_query("Change it to a two-week review.", history)

    assert "Use the NIST approach for the checklist." in query
    assert query.endswith("Current follow-up: Change it to a two-week review.")


def test_contextualize_followup_query_leaves_standalone_request_unchanged():
    query = "Explain the documentation requirements for high-risk AI systems."
    assert (
        contextualize_followup_query(
            query, [{"role": "user", "content": "Unrelated earlier request."}]
        )
        == query
    )


def test_clean_retrieval_query_removes_synthetic_wrapper_and_tail():
    query = (
        "Here is a rewritten scenario that meets the requirements:\n\n"
        "A compliance officer evaluates the NIST AI RMF.\n\n"
        "This rewritten scenario meets the requirements by adding constraints."
    )
    assert clean_retrieval_query(query) == (
        "A compliance officer evaluates the NIST AI RMF."
    )


def test_build_retrieval_queries_preserves_original_as_fallback():
    query = "Here is a rewritten scenario: A team applies the EU AI Act."
    assert build_retrieval_queries(query) == [
        "A team applies the EU AI Act.",
        query,
    ]


def test_reciprocal_rank_fusion_deduplicates_and_rewards_consensus():
    first = [
        {"uuid": "a", "score": 0.8},
        {"uuid": "b", "score": 0.7},
    ]
    second = [
        {"uuid": "b", "score": 0.9},
        {"uuid": "c", "score": 0.6},
    ]
    fused = reciprocal_rank_fusion([first, second], rank_constant=60)
    assert [row["uuid"] for row in fused] == ["b", "a", "c"]
    assert fused[0]["hybrid_score"] == 0.9


def test_expand_multilingual_query_preserves_frameworks_and_adds_translation():
    query = "A NIST AI RMF review covers data protection and human rights."
    expanded = expand_multilingual_query(query)

    assert "NIST" in expanded
    assert "AI RMF" in expanded
    assert "proteção de dados" in expanded
    assert "direitos humanos" in expanded


def test_build_retrieval_queries_can_add_weighted_expansion():
    original = "Here is a rewritten scenario: Review privacy under the EU AI Act."
    queries = build_retrieval_queries(original, expand=True)

    assert len(queries) == 3
    assert "privacidade" in queries[1]
    assert retrieval_query_weights(
        original, queries, original_weight=0.1, expansion_weight=0.7
    ) == [1.0, 0.7, 0.1]
