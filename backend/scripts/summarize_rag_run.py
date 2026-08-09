"""Upsert one compact local RAG comparison row from DeepEval's rolling JSON."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--top-k", type=int, required=True)
    parser.add_argument("--candidate-floor", type=int, required=True)
    parser.add_argument("--query-expansion", type=int, choices=(0, 1), required=True)
    parser.add_argument("--metadata-weight", type=float, required=True)
    args = parser.parse_args()

    payload = json.loads(args.source.read_text(encoding="utf-8"))
    if payload.get("identifier") != args.run_id:
        raise SystemExit(
            f"Rolling DeepEval run is {payload.get('identifier')!r}, "
            f"not requested run {args.run_id!r}"
        )
    scores: dict[str, list[float]] = defaultdict(list)
    passes: dict[str, int] = defaultdict(int)
    for case in payload.get("testCases", []):
        for metric in case.get("metricsData", []):
            score = metric.get("score")
            if score is not None:
                scores[metric["name"]].append(float(score))
            passes[metric["name"]] += int(bool(metric.get("success")))

    case_count = len(payload.get("testCases", []))
    row = {
        "run_id": args.run_id,
        "alpha": args.alpha,
        "top_k": args.top_k,
        "candidate_floor": args.candidate_floor,
        "query_expansion": bool(args.query_expansion),
        "metadata_weight": args.metadata_weight,
        "cases": case_count,
        "case_passed": payload.get("testPassed", 0),
        "case_pass_rate": (
            payload.get("testPassed", 0) / case_count if case_count else 0.0
        ),
        "metrics": {
            name: {
                "mean": statistics.mean(values) if values else None,
                "median": statistics.median(values) if values else None,
                "passed": passes[name],
                "pass_rate": passes[name] / case_count if case_count else 0.0,
            }
            for name, values in scores.items()
        },
    }

    comparison = {"runs": []}
    if args.destination.exists():
        comparison = json.loads(args.destination.read_text(encoding="utf-8"))
    comparison["runs"] = [
        existing
        for existing in comparison.get("runs", [])
        if existing.get("run_id") != args.run_id
    ]
    comparison["runs"].append(row)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(
        json.dumps(comparison, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(row, indent=2))


if __name__ == "__main__":
    main()
