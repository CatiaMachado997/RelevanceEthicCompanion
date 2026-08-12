from services.text_chunking import (
    detect_language,
    embedding_text,
    structure_aware_chunks,
)


def test_structure_aware_chunks_tracks_heading_and_word_bound():
    text = "# Governance\n\n" + "Risk controls are reviewed monthly. " * 40
    chunks = structure_aware_chunks(text, max_words=30, overlap_words=5)
    assert len(chunks) > 1
    assert all(len(chunk.content.split()) <= 30 for chunk in chunks)
    assert all(chunk.section_title == "Governance" for chunk in chunks)


def test_embedding_text_adds_structure_without_mutating_content():
    chunk = structure_aware_chunks(
        "# Transparency\n\nDocument model limitations clearly.",
        max_words=20,
        overlap_words=2,
    )[0]
    enriched = embedding_text(chunk, title="AI policy")
    assert enriched.startswith("Document: AI policy\nSection: Transparency\n")
    assert chunk.content == "Document model limitations clearly."


def test_detect_language_handles_portuguese_and_english():
    assert (
        detect_language("O regulamento de IA da União Europeia não permite isso")
        == "pt"
    )
    assert detect_language("The AI governance framework manages risks") == "en"
