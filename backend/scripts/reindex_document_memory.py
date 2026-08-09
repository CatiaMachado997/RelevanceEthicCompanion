"""Re-embed DocumentMemory objects in place without creating index copies."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings
from services.embedding_service import EmbeddingService
from services.text_chunking import TextChunk, detect_language, embedding_text
from utils.weaviate_client import get_weaviate_client


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")

    embedder = EmbeddingService(
        provider="ollama",
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )
    weaviate = get_weaviate_client()
    if weaviate is None:
        raise SystemExit("Weaviate is unavailable")
    weaviate.ensure_document_memory_properties()
    collection = weaviate.client.collections.get("DocumentMemory")

    pending = []
    skipped = 0
    for item in collection.iterator():
        properties = dict(item.properties or {})
        if not args.force and properties.get("embedding_model") == embedder.model:
            skipped += 1
            continue
        content = str(properties.get("content") or "").strip()
        if not content:
            skipped += 1
            continue
        properties.setdefault("section_title", "")
        properties.setdefault("language", detect_language(content))
        properties.setdefault("document_version", "")
        pending.append((item.uuid, properties))

    print(
        f"reindex plan: update={len(pending)} skip={skipped} "
        f"model={embedder.model} dry_run={args.dry_run}",
        flush=True,
    )
    if args.dry_run or not pending:
        weaviate.client.close()
        return

    updated = 0
    for offset in range(0, len(pending), args.batch_size):
        batch = pending[offset : offset + args.batch_size]
        texts = [
            embedding_text(
                TextChunk(
                    str(properties["content"]),
                    str(properties.get("section_title") or ""),
                ),
                title=str(properties.get("filename") or ""),
            )
            for _, properties in batch
        ]
        vectors = await embedder.generate_embeddings_batch(
            texts, batch_size=args.batch_size
        )
        for (object_id, properties), vector in zip(batch, vectors):
            properties["embedding_model"] = embedder.model
            collection.data.replace(
                uuid=object_id,
                properties=properties,
                vector=vector,
            )
            updated += 1
        print(f"updated {updated}/{len(pending)}", flush=True)
    weaviate.client.close()


if __name__ == "__main__":
    asyncio.run(main())
