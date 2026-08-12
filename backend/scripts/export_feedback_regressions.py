"""Export the latest negative chat feedback into one local regression dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from utils.db import get_db_connection

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "tests/evals/synthetic_data/feedback_regressions.json"
)


def export_feedback(user_id: str) -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (item_id)
                    id, item_id, feedback_type, context_snapshot,
                    additional_notes, corrected_answer, timestamp
                FROM relevance_feedback
                WHERE user_id = %s
                  AND item_type = 'chat_response'
                  AND feedback_type IN (
                      'thumbs_down', 'not_relevant', 'value_conflict', 'inaccurate'
                  )
                ORDER BY item_id, timestamp DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()

    cases: list[dict] = []
    for row in rows:
        snapshot = row.get("context_snapshot") or {}
        metadata = snapshot.get("answer_metadata") or {}
        sources = metadata.get("document_sources") or []
        cases.append(
            {
                "input": snapshot.get("prompt") or "",
                "actual_output": snapshot.get("answer") or "",
                "expected_output": row.get("corrected_answer"),
                "retrieval_context": [
                    source.get("snippet") or source.get("content") or ""
                    for source in sources
                    if isinstance(source, dict)
                ],
                "metadata": {
                    "feedback_id": str(row["id"]),
                    "answer_turn_id": str(row["item_id"]),
                    "feedback_type": row["feedback_type"],
                    "user_notes": row.get("additional_notes"),
                    "timestamp": row["timestamp"].isoformat(),
                },
            }
        )
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    cases = export_feedback(args.user_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(cases, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(f"Exported {len(cases)} regression cases to {args.output}")


if __name__ == "__main__":
    main()
