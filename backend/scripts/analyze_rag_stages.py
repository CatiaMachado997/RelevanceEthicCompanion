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


def _source_flags(
    rows: list[dict], expected_source_name: str, top_k: int
) -> list[bool]:
    expected = expected_source_name.casefold()
    found = False
    flags: list[bool] = []
    for row in rows[:top_k]:
        filename = str(row.get("filename") or "").rsplit("/", 1)[-1].casefold()
        relevant = filename == expected and not found
        flags.append(relevant)
        found = found or relevant
    return flags


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


def _rank_distribution(ranks: list[int | None]) -> dict[str, int]:
    buckets = {
        "rank_1": 0,
        "rank_2_3": 0,
        "rank_4_5": 0,
        "rank_6_10": 0,
        "rank_11_20": 0,
        "missing": 0,
    }
    for rank in ranks:
        if rank is None:
            buckets["missing"] += 1
        elif rank == 1:
            buckets["rank_1"] += 1
        elif rank <= 3:
            buckets["rank_2_3"] += 1
        elif rank <= 5:
            buckets["rank_4_5"] += 1
        elif rank <= 10:
            buckets["rank_6_10"] += 1
        else:
            buckets["rank_11_20"] += 1
    return buckets


async def main() -> None:
    rows: list[dict] = []
    shard_dir = Path(
        os.getenv(
            "RAG_EVAL_DATA_DIR",
            str(BACKEND_DIR / "tests/evals/synthetic_data"),
        )
    )
    for shard in sorted(shard_dir.glob("rag_[0-9]*_[0-9]*.json")):
        rows.extend(json.loads(shard.read_text()))
    limit = int(os.getenv("RAG_STAGE_LIMIT", str(len(rows))))
    rows = rows[:limit]
    manifest_path = Path(
        os.getenv(
            "RAG_EVAL_MANIFEST",
            str(shard_dir.parent / "contexts.manifest.json"),
        )
    )
    source_contexts = json.loads(manifest_path.read_text()).get("contexts") or []
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

    source_stage_flags: dict[str, list[list[bool]]] = {
        "original-hybrid": [],
        "cleaned-hybrid": [],
        "rrf-fusion": [],
        "local-rerank": [],
        "diversity": [],
    }
    candidate_ranks: list[int | None] = []
    difficult_examples: list[dict] = []
    example_limit = int(os.getenv("RAG_STAGE_EXAMPLE_LIMIT", "0"))
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
        expected_source_name = source_contexts[case_index // 2]["source_name"]
        candidate_rank = next(
            (
                index
                for index, row in enumerate(original[:candidate_limit], start=1)
                if str(row.get("filename") or "").rsplit("/", 1)[-1].casefold()
                == expected_source_name.casefold()
            ),
            None,
        )
        candidate_ranks.append(candidate_rank)
        if (
            example_limit
            and candidate_rank != 1
            and len(difficult_examples) < example_limit
        ):
            difficult_examples.append(
                {
                    "case_index": case_index,
                    "query": query[:240],
                    "expected_source_name": expected_source_name,
                    "expected_rank": candidate_rank,
                    "top_candidates": [
                        {
                            "document_id": row.get("document_id"),
                            "filename": row.get("filename"),
                            "score": row.get("score"),
                            "snippet": str(row.get("snippet") or "")[:160],
                        }
                        for row in original[:5]
                    ],
                }
            )
        for name, result in (
            ("original-hybrid", original),
            ("cleaned-hybrid", cleaned),
            ("rrf-fusion", fused),
            ("local-rerank", reranked),
            ("diversity", diverse),
        ):
            source_stage_flags[name].append(
                _source_flags(result, expected_source_name, top_k)
            )

    print(
        json.dumps(
            {
                "source_stages": {
                    name: _summary(flags) for name, flags in source_stage_flags.items()
                },
                "source_candidate_rank_distribution": _rank_distribution(
                    candidate_ranks
                ),
                "difficult_examples": difficult_examples,
            },
            indent=2,
        )
    )
    weaviate.client.close()


if __name__ == "__main__":
    asyncio.run(main())
