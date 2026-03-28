# backend/tests/test_document_processor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.document_processor import DocumentProcessor, chunk_text


# ── chunk_text ──────────────────────────────────────────────────────────────

def test_chunk_text_short_document():
    """Short text should produce exactly one chunk."""
    text = "Hello world. This is a short document."
    chunks = chunk_text(text, chunk_size=2000, overlap=200)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_splits_long_document():
    """Long text should be split into multiple chunks."""
    text = "word " * 1000  # ~5000 chars
    chunks = chunk_text(text, chunk_size=2000, overlap=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 2000 + 200


def test_chunk_text_overlap():
    """Consecutive chunks should share overlapping content."""
    text = "a" * 100 + " " + "b" * 100 + " " + "c" * 100
    chunks = chunk_text(text, chunk_size=150, overlap=50)
    assert len(chunks) >= 2
    if len(chunks) >= 2:
        tail = chunks[0][-50:]
        head = chunks[1][:50]
        assert len(tail) > 0 and len(head) > 0


def test_chunk_text_empty():
    """Empty text should return an empty list."""
    chunks = chunk_text("", chunk_size=2000, overlap=200)
    assert chunks == []


def test_chunk_text_whitespace_only():
    """Whitespace-only text should return empty list."""
    chunks = chunk_text("   \n\t  ", chunk_size=2000, overlap=200)
    assert chunks == []


# ── extract_text ────────────────────────────────────────────────────────────

def test_extract_text_plain():
    """Plain text bytes should be decoded and returned as-is."""
    processor = DocumentProcessor(context_manager=MagicMock(), embedding_service=MagicMock())
    text = processor.extract_text(b"Hello, world!", "text/plain")
    assert text == "Hello, world!"


def test_extract_text_unsupported():
    """Unsupported content type should raise ValueError."""
    processor = DocumentProcessor(context_manager=MagicMock(), embedding_service=MagicMock())
    with pytest.raises(ValueError, match="Unsupported"):
        processor.extract_text(b"data", "image/png")
