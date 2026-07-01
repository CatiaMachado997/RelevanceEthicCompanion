# Context Scoring — Program Guidance

## Objective
Maximize mean NDCG@5 across 50 fixed (query, expected_keywords) test pairs.
NDCG@5 = 1.0 means the expected content appears at rank 1 for every query.

## Constraints
- Only edit numeric/string values in WeaviateConfig
- Do NOT change field names
- alpha must stay in [0.0, 1.0]
- limit must be an integer in [5, 50]
- certainty must stay in [0.0, 1.0]
- distance_metric must be "cosine", "dot", or "l2-squared"

## What Each Parameter Does
- alpha: 0.0 = pure BM25 (keyword match), 1.0 = pure vector (semantic). 0.5 = balanced hybrid.
- limit: How many results to retrieve. More = better recall but slower.
- certainty: Minimum similarity to include. Higher = more precise, fewer results.
- distance_metric: How vector similarity is computed.
