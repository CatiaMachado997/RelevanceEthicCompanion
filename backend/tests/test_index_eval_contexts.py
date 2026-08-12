from scripts.index_eval_contexts import evaluation_document_id


def test_evaluation_document_id_groups_contexts_from_same_source():
    source = {
        "source_path": "authoritative/nist-ai-rmf-1.0.pdf",
        "source_name": "nist-ai-rmf-1.0.pdf",
    }

    assert evaluation_document_id(source, 2) == evaluation_document_id(source, 53)


def test_evaluation_document_id_separates_different_sources():
    left = {"source_path": "authoritative/nist-ai-rmf-1.0.pdf"}
    right = {"source_path": "authoritative/nist-ai-600-1-genai-profile.pdf"}

    assert evaluation_document_id(left, 0) != evaluation_document_id(right, 0)


def test_evaluation_document_id_has_stable_context_fallback():
    assert evaluation_document_id({}, 7) == evaluation_document_id({}, 7)
    assert evaluation_document_id({}, 7) != evaluation_document_id({}, 8)
