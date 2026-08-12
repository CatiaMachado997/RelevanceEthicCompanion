"""Compare retrieval stages without writing a new DeepEval result artifact."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings
from services.embedding_service import EmbeddingService
from services.rag_query import (
    build_retrieval_queries,
    reciprocal_rank_fusion,
    retrieval_query_weights,
)
from services.rag_retrieval import RagRetrievalService, select_diverse_results
from services.rerank import local_rerank
from utils.weaviate_client import get_weaviate_client


def _normalize(text: str) -> str:
    return " ".join(str(text).lower().split())


def _flags(rows: list[dict], expected_document_id: str, top_k: int) -> list[bool]:
    return [
        str(row.get("document_id") or "") == expected_document_id
        for row in rows[:top_k]
    ]


def _summary(all_flags: list[list[bool]]) -> dict[str, float]:
    average_precision = []
    for flags in all_flags:
        precisions = [
            sum(flags[: index + 1]) / (index + 1)
            for index, relevant in enumerate(flags)
            if relevant
        ]
        average_precision.append(
            sum(precisions) / len(precisions) if precisions else 0.0
        )
    hits = [bool(sum(flags)) for flags in all_flags]
    reciprocal_ranks = [
        next((1 / (index + 1) for index, flag in enumerate(flags) if flag), 0)
        for flags in all_flags
    ]
    return {
        "average_precision": sum(average_precision) / len(average_precision),
        "hit_rate": sum(hits) / len(hits),
        "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks),
    }


async def main() -> None:
    rows: list[dict] = []
    for shard in sorted((BACKEND_DIR / "tests/evals/synthetic_data").glob("*.json")):
        rows.extend(json.loads(shard.read_text()))
    limit = int(os.getenv("RAG_STAGE_LIMIT", str(len(rows))))
    rows = rows[:limit]
    top_k = int(os.getenv("RAG_EVAL_TOP_K", "3"))
    candidate_limit = int(os.getenv("RAG_CANDIDATE_FLOOR", "20"))
    query_expansion = os.getenv("RAG_QUERY_EXPANSION", "0") == "1"
    expansion_weight = float(os.getenv("RAG_QUERY_EXPANSION_WEIGHT", "0.8"))

    embedder = EmbeddingService(
        provider="ollama",
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )
    weaviate = get_weaviate_client()
    if weaviate is None:
        raise SystemExit("Weaviate is unavailable")

    stage_flags: dict[str, list[list[bool]]] = {
        "original-hybrid": [],
        "cleaned-hybrid": [],
        "rrf-fusion": [],
        "local-rerank": [],
        "diversity": [],
    }
    for case_index, golden in enumerate(rows):
        query = golden["scenario"]
        queries = build_retrieval_queries(query, expand=query_expansion)
        ranked_lists = []
        for retrieval_query in queries:
            vector = await embedder.generate_query_embedding(retrieval_query)
            raw = weaviate.hybrid_search(
                collection="DocumentMemory",
                query=retrieval_query,
                query_vector=vector,
                user_id=str(settings.DEV_USER_ID),
                limit=candidate_limit,
                alpha=0.5,
                embedding_model=embedder.model,
            )
            ranked_lists.append([RagRetrievalService._format(item) for item in raw])
        original = ranked_lists[-1]
        cleaned = ranked_lists[0]
        fused = [
            RagRetrievalService._format(item)
            for item in reciprocal_rank_fusion(
                [
                    [
                        {
                            "uuid": row["chunk_uuid"],
                            "score": row["score"],
                            "properties": {
                                "content": row["snippet"],
                                "document_id": row["document_id"],
                                "filename": row["filename"],
                                "chunk_index": row["chunk_index"],
                                "source_type": row["source_type"],
                                "section_title": row.get("section_title", ""),
                                "language": row.get("language", ""),
                                "document_version": row.get("document_version", ""),
                            },
                        }
                        for row in ranked
                    ]
                    for ranked in ranked_lists
                ],
                weights=retrieval_query_weights(
                    query,
                    queries,
                    original_weight=settings.RAG_ORIGINAL_QUERY_WEIGHT,
                    expansion_weight=expansion_weight,
                ),
            )
        ]
        reranked = local_rerank(queries[0], fused, top_k=len(fused))
        diverse = select_diverse_results(reranked, top_k=top_k)
        expected_document_id = f"eval-context-{case_index // 2:03d}"
        for name, result in (
            ("original-hybrid", original),
            ("cleaned-hybrid", cleaned),
            ("rrf-fusion", fused),
            ("local-rerank", reranked),
            ("diversity", diverse),
        ):
            stage_flags[name].append(_flags(result, expected_document_id, top_k))

    print(
        json.dumps(
            {name: _summary(flags) for name, flags in stage_flags.items()}, indent=2
        )
    )
    weaviate.client.close()


if __name__ == "__main__":
    asyncio.run(main())
