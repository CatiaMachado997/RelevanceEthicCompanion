"""Mutable surface for context relevance scoring track.

Controls Weaviate hybrid search parameters.
The agent edits only these values to improve NDCG@5.
"""

from dataclasses import dataclass


@dataclass
class WeaviateConfig:
    alpha: float = 0.5           # BM25/vector balance: 0.0 = pure BM25, 1.0 = pure vector
    limit: int = 10              # number of results to retrieve
    certainty: float = 0.7       # minimum similarity threshold
    distance_metric: str = "cosine"  # "cosine" | "dot" | "l2-squared"


config = WeaviateConfig()
