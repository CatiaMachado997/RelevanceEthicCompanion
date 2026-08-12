"""Idempotently index generated evaluation contexts into local Weaviate."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings
from services.embedding_service import EmbeddingService
from services.text_chunking import (
    TextChunk,
    detect_language,
    embedding_text,
    structure_aware_chunks,
)
from utils.weaviate_client import get_weaviate_client

COLLECTION = "DocumentMemory"
NAMESPACE = uuid.UUID("f57042c5-72e5-4d92-989f-02ee0c8b0e47")
CHUNK_SIZE = 400
CHUNK_OVERLAP = 60


def chunk_text(text: str) -> list[str]:
    return [
        chunk.content
        for chunk in structure_aware_chunks(
            text, max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP
        )
    ]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("contexts", type=Path)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--user-id", default=settings.DEV_USER_ID)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    contexts = json.loads(args.contexts.read_text(encoding="utf-8"))[: args.limit]
    manifest_path = args.contexts.with_suffix(".manifest.json")
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )
    context_sources = manifest.get("contexts") or []

    def source_metadata(context_index: int) -> dict[str, str]:
        return (
            context_sources[context_index]
            if context_index < len(context_sources)
            else {}
        )

    def source_name(context_index: int) -> str:
        return source_metadata(context_index).get("source_name") or (
            f"evaluation-context-{context_index:03d}.txt"
        )

    rows: list[tuple[str, int, int, TextChunk, str]] = []
    for context_index, context in enumerate(contexts):
        source_chunks = context if isinstance(context, list) else [str(context)]
        chunk_index = 0
        for source in source_chunks:
            language = detect_language(str(source))
            for chunk in structure_aware_chunks(
                str(source), max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP
            ):
                rows.append(
                    (
                        f"eval-context-{context_index:03d}",
                        context_index,
                        chunk_index,
                        chunk,
                        language,
                    )
                )
                chunk_index += 1

    embedder = EmbeddingService(
        provider="ollama",
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )
    vectors = await embedder.generate_embeddings_batch(
        [
            embedding_text(row[3], title=source_name(row[1]))
            for row in rows
        ],
        batch_size=args.batch_size,
    )

    weaviate = get_weaviate_client()
    if weaviate is None:
        raise SystemExit("Weaviate is unavailable")
    weaviate.ensure_document_memory_properties()
    collection = weaviate.client.collections.get(COLLECTION)
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    replaced = 0

    chunk_counts: dict[str, int] = {}
    for document_id, _, _, _, _ in rows:
        chunk_counts[document_id] = chunk_counts.get(document_id, 0) + 1

    # Replace each document atomically at the logical level so changed chunk
    # boundaries or embedding models never leave stale duplicate chunks.
    for document_id in chunk_counts:
        weaviate.delete_by_filter(
            COLLECTION,
            {"user_id": str(args.user_id), "document_id": document_id},
        )

    for row, vector in zip(rows, vectors):
        document_id, context_index, chunk_index, chunk, language = row
        object_id = uuid.uuid5(NAMESPACE, f"{args.user_id}:{document_id}:{chunk_index}")
        source = source_metadata(context_index)
        filename = source_name(context_index)
        properties = {
            "user_id": str(args.user_id),
            "content": chunk.content,
            "document_id": document_id,
            "filename": filename,
            "chunk_index": chunk_index,
            "chunk_count": chunk_counts[document_id],
            "source_type": "evaluation",
            "embedding_model": embedder.model,
            "section_title": chunk.section_title,
            "language": language,
            "document_version": source.get("source_path") or "",
            "created_at": now,
        }
        if collection.data.exists(object_id):
            collection.data.replace(
                uuid=object_id, properties=properties, vector=vector
            )
            replaced += 1
        else:
            collection.data.insert(uuid=object_id, properties=properties, vector=vector)
            inserted += 1

    print(
        f"indexed {len(rows)} chunks for {len(contexts)} contexts "
        f"(inserted={inserted}, replaced={replaced}, dimension={len(vectors[0])})"
    )


if __name__ == "__main__":
    asyncio.run(main())
