"""Structure-aware, dependency-free chunking shared by every RAG indexer."""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_MAX_WORDS = 400
DEFAULT_OVERLAP_WORDS = 60
_HEADING = re.compile(r"^(?:#{1,6}\s+.+|[A-ZÀ-Ý][^.!?]{2,90}:?)$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class TextChunk:
    content: str
    section_title: str = ""


def normalize_document_text(text: str) -> str:
    """Normalize extraction noise without flattening paragraph structure."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in (text or "").splitlines()]
    normalized: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if normalized and not blank:
                normalized.append("")
            blank = True
            continue
        normalized.append(line)
        blank = False
    return "\n".join(normalized).strip()


def detect_language(text: str) -> str:
    """Return a small, useful language hint for the current English/Portuguese KB."""
    sample = f" {text[:4000].lower()} "
    portuguese_markers = (
        " de ",
        " da ",
        " do ",
        " para ",
        " que ",
        " não ",
        " regulamento ",
    )
    return "pt" if sum(marker in sample for marker in portuguese_markers) >= 3 else "en"


def _units(text: str) -> list[tuple[str, str]]:
    section = ""
    output: list[tuple[str, str]] = []
    for block in re.split(r"\n\s*\n", normalize_document_text(text)):
        block = block.strip()
        if not block:
            continue
        if "\n" not in block and _HEADING.match(block) and len(block.split()) <= 14:
            section = block.lstrip("# ").rstrip(":").strip()
            continue
        for sentence in _SENTENCE_END.split(re.sub(r"\s+", " ", block)):
            if sentence.strip():
                output.append((sentence.strip(), section))
    return output


def structure_aware_chunks(
    text: str,
    *,
    max_words: int = DEFAULT_MAX_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> list[TextChunk]:
    """Chunk on headings/sentences, with bounded word overlap for continuity."""
    if max_words < 1 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("Require max_words > overlap_words >= 0")
    units = _units(text)
    if not units:
        return []

    chunks: list[TextChunk] = []
    words: list[str] = []
    section = ""

    def flush() -> None:
        nonlocal words
        if words:
            chunks.append(TextChunk(" ".join(words).strip(), section))
            words = words[-overlap_words:] if overlap_words else []

    for sentence, sentence_section in units:
        sentence_words = sentence.split()
        if sentence_section and sentence_section != section and words:
            flush()
        section = sentence_section or section
        while sentence_words:
            capacity = max_words - len(words)
            if capacity <= 0:
                flush()
                capacity = max_words - len(words)
            words.extend(sentence_words[:capacity])
            sentence_words = sentence_words[capacity:]
            if sentence_words:
                flush()
    flush()

    # A final overlap-only tail contains no new information.
    if (
        overlap_words
        and len(chunks) > 1
        and chunks[-1].content.split() == chunks[-2].content.split()[-overlap_words:]
    ):
        chunks.pop()
    return chunks


def embedding_text(chunk: TextChunk, *, title: str = "") -> str:
    """Enrich vectors with document structure while keeping stored content clean."""
    parts = []
    if title:
        parts.append(f"Document: {title}")
    if chunk.section_title:
        parts.append(f"Section: {chunk.section_title}")
    parts.append(chunk.content)
    return "\n".join(parts)
