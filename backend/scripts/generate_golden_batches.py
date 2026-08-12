"""Generate a resumable 200-case DeepEval dataset in small provider batches."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

SHARD_PATTERN = re.compile(r"rag_(\d+)_(\d+)\.json")
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{3,}")
STOPWORDS = {
    "about",
    "after",
    "also",
    "between",
    "could",
    "different",
    "discuss",
    "expected",
    "from",
    "have",
    "into",
    "more",
    "outcome",
    "should",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "using",
    "were",
    "while",
    "with",
    "would",
}
PROMPT_LEAKAGE = (
    "here is a rewritten scenario",
    "preserving factual correctness",
    "this rewritten scenario",
    "stays under 60 words",
)


def load_rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    for key in ("goldens", "conversational_goldens", "data"):
        if isinstance(payload.get(key), list):
            return payload[key]
    raise ValueError(f"Unsupported DeepEval output shape: {path}")


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in TOKEN_PATTERN.findall(value.casefold())
        if token not in STOPWORDS
    }


def validate_grounding(
    rows: list[dict],
    minimum_overlap: int = 2,
    semantic_similarity: Callable[[str, str], float] | None = None,
    semantic_threshold: float = 0.50,
) -> None:
    """Reject generated cases that are not lexically anchored to their context."""
    for position, row in enumerate(rows, start=1):
        context = row.get("context") or []
        if isinstance(context, str):
            context = [context]
        context_tokens = _content_tokens(" ".join(context))
        field_tokens: dict[str, set[str]] = {}
        for field in ("scenario", "expected_outcome"):
            field_value = str(row.get(field) or "")
            if any(marker in field_value.casefold() for marker in PROMPT_LEAKAGE):
                raise ValueError(
                    f"Golden {position} field {field!r} leaked generation instructions"
                )
            field_tokens[field] = _content_tokens(field_value)

        scenario_overlap = context_tokens.intersection(field_tokens["scenario"])
        context_value = "\n".join(context)
        scenario_value = str(row.get("scenario") or "")
        scenario_similarity = None
        if len(scenario_overlap) < minimum_overlap and semantic_similarity:
            scenario_similarity = semantic_similarity(scenario_value, context_value)
        if len(scenario_overlap) < minimum_overlap and (
            scenario_similarity is None or scenario_similarity < semantic_threshold
        ):
            raise ValueError(
                f"Golden {position} field 'scenario' is not grounded: "
                f"only {len(scenario_overlap)} informative context tokens overlap"
                + (
                    ""
                    if scenario_similarity is None
                    else f"; semantic similarity {scenario_similarity:.3f}"
                )
            )

        outcome_anchors = context_tokens.union(field_tokens["scenario"])
        outcome_overlap = outcome_anchors.intersection(
            field_tokens["expected_outcome"]
        )
        outcome_similarity = None
        if len(outcome_overlap) < minimum_overlap and semantic_similarity:
            outcome_similarity = semantic_similarity(
                str(row.get("expected_outcome") or ""),
                f"{scenario_value}\n{context_value}",
            )
        if len(outcome_overlap) < minimum_overlap and (
            outcome_similarity is None or outcome_similarity < semantic_threshold
        ):
            raise ValueError(
                f"Golden {position} field 'expected_outcome' is not grounded: "
                f"only {len(outcome_overlap)} informative source/scenario tokens overlap"
                + (
                    ""
                    if outcome_similarity is None
                    else f"; semantic similarity {outcome_similarity:.3f}"
                )
            )


def ollama_semantic_similarity(left: str, right: str) -> float:
    """Return cross-lingual cosine similarity using the existing local embedder."""
    import ollama

    client = ollama.Client(
        host=os.getenv("LOCAL_MODEL_BASE_URL", "http://127.0.0.1:11434")
    )
    response = client.embed(
        model=os.getenv("LOCAL_EMBEDDING_MODEL_NAME", "bge-m3:latest"),
        input=[left, right],
    )
    left_vector, right_vector = response.embeddings
    numerator = sum(a * b for a, b in zip(left_vector, right_vector))
    denominator = math.sqrt(sum(a * a for a in left_vector)) * math.sqrt(
        sum(b * b for b in right_vector)
    )
    return numerator / denominator if denominator else 0.0


def inspect_shards(output_dir: Path, context_count: int) -> tuple[set[int], int]:
    """Validate canonical shards and return covered context indexes and row count."""
    covered: set[int] = set()
    row_count = 0
    for shard in sorted(output_dir.glob("rag_[0-9]*_[0-9]*.json")):
        match = SHARD_PATTERN.fullmatch(shard.name)
        if match is None:
            continue
        start, end = (int(value) for value in match.groups())
        if start > end or end >= context_count:
            raise ValueError(f"Invalid shard range in {shard}")
        indexes = set(range(start, end + 1))
        overlap = covered.intersection(indexes)
        if overlap:
            raise ValueError(
                f"Overlapping shard {shard}; contexts already covered: {sorted(overlap)}"
            )
        expected = len(indexes) * 2
        actual = len(load_rows(shard))
        if actual != expected:
            raise ValueError(f"{shard} has {actual} goldens; expected {expected}")
        covered.update(indexes)
        row_count += actual
    return covered, row_count


def audit_shard_grounding(
    output_dir: Path,
    semantic_similarity: Callable[[str, str], float] | None = None,
    semantic_threshold: float = 0.50,
) -> list[tuple[Path, str]]:
    """Return every canonical shard that fails grounding validation."""
    failures: list[tuple[Path, str]] = []
    for shard in sorted(output_dir.glob("rag_[0-9]*_[0-9]*.json")):
        try:
            validate_grounding(
                load_rows(shard),
                semantic_similarity=semantic_similarity,
                semantic_threshold=semantic_threshold,
            )
        except ValueError as error:
            failures.append((shard, str(error)))
    return failures


def missing_batches(
    context_count: int, covered: set[int], batch_size: int
) -> list[list[int]]:
    """Group uncovered, consecutive context indexes without changing old shards."""
    missing = [index for index in range(context_count) if index not in covered]
    batches: list[list[int]] = []
    for index in missing:
        if (
            not batches
            or len(batches[-1]) >= batch_size
            or index != batches[-1][-1] + 1
        ):
            batches.append([index])
        else:
            batches[-1].append(index)
    return batches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("contexts", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument(
        "--provider", choices=("ollama", "openai", "groq"), default="ollama"
    )
    parser.add_argument(
        "--max-new-batches",
        type=int,
        help="Stop after this many newly generated batches (completed shards are skipped)",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        help="Pause between batches (defaults to 65 seconds for Groq, otherwise 0)",
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument(
        "--strict-grounding-style",
        action="store_true",
        help="Ask DeepEval to rewrite scenarios using only supplied source topics",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Validate every existing shard without generating new cases",
    )
    args = parser.parse_args()

    if args.max_new_batches is not None and args.max_new_batches < 1:
        parser.error("--max-new-batches must be at least 1")
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    if args.retry_attempts < 1:
        parser.error("--retry-attempts must be at least 1")

    delay_seconds = args.delay_seconds
    if delay_seconds is None:
        delay_seconds = 65.0 if args.provider == "groq" else 0.0
    if delay_seconds < 0:
        parser.error("--delay-seconds cannot be negative")

    contexts = json.loads(args.contexts.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    semantic_threshold = float(
        os.getenv("RAG_GOLDEN_SEMANTIC_THRESHOLD", "0.50")
    )
    semantic_similarity = (
        ollama_semantic_similarity if args.provider == "ollama" else None
    )
    if args.audit_only:
        failures = audit_shard_grounding(
            args.output_dir,
            semantic_similarity=semantic_similarity,
            semantic_threshold=semantic_threshold,
        )
        for shard, error in failures:
            print(f"FAIL {shard.name}: {error}")
        if failures:
            raise SystemExit(f"{len(failures)} shard(s) failed grounding audit")
        print("all canonical shards passed grounding audit")
        return
    launcher_name = (
        "deepeval_local.sh"
        if args.provider == "ollama"
        else f"deepeval_{args.provider}.sh"
    )
    launcher = Path(__file__).with_name(launcher_name)

    covered, existing_rows = inspect_shards(args.output_dir, len(contexts))
    print(
        f"validated existing coverage: {len(covered)}/{len(contexts)} contexts "
        f"({existing_rows} goldens)",
        flush=True,
    )

    generated_batches = 0
    for indexes in missing_batches(len(contexts), covered, args.batch_size):
        start, end = indexes[0], indexes[-1]
        batch = [contexts[index] for index in indexes]
        name = f"rag_{start:03d}_{end:03d}"
        destination = args.output_dir / f"{name}.json"
        expected = len(batch) * 2

        with tempfile.TemporaryDirectory(prefix="ethic-rag-eval-") as temp_dir:
            context_file = Path(temp_dir) / "contexts.json"
            context_file.write_text(
                json.dumps(batch, ensure_ascii=False), encoding="utf-8"
            )
            command = [
                str(launcher),
                "generate",
                "--method",
                "contexts",
                "--variation",
                "multi-turn",
                "--contexts-file",
                str(context_file),
                "--max-goldens-per-context",
                "2",
                "--include-expected",
                "--output-dir",
                str(args.output_dir),
                "--file-type",
                "json",
                "--file-name",
                name,
            ]
            if args.provider == "openai":
                command.extend(["--async-mode", "--max-concurrent", "5"])
            else:
                command.append("--sync-mode")
            if args.strict_grounding_style:
                command.extend(
                    [
                        "--scenario-context",
                        (
                            "A concrete discussion of the supplied source's ethical "
                            "AI requirements. Use only topics present in the source."
                        ),
                        "--conversational-task",
                        (
                            "Apply or explain the source guidance without introducing "
                            "outside facts."
                        ),
                        "--participant-roles",
                        "An AI governance practitioner and an ethical AI advisor.",
                        "--scenario-format",
                        "One concise scenario only; no prompt commentary.",
                        "--expected-outcome-format",
                        "A concise outcome grounded only in the supplied source.",
                    ]
                )
            for attempt in range(1, args.retry_attempts + 1):
                try:
                    subprocess.run(command, check=True)
                    if not destination.exists():
                        raise ValueError(f"Batch {name} did not create its shard")
                    rows = load_rows(destination)
                    if len(rows) != expected:
                        raise ValueError(
                            f"Batch {name} produced {len(rows)} goldens; "
                            f"expected {expected}"
                        )
                    validate_grounding(
                        rows,
                        semantic_similarity=semantic_similarity,
                        semantic_threshold=semantic_threshold,
                    )
                    break
                except (subprocess.CalledProcessError, ValueError) as error:
                    destination.unlink(missing_ok=True)
                    if attempt == args.retry_attempts:
                        raise
                    print(
                        f"batch {name} rejected ({error}); retrying in "
                        f"{delay_seconds:g}s "
                        f"({attempt}/{args.retry_attempts})",
                        flush=True,
                    )
                    time.sleep(delay_seconds)
        generated_batches += 1
        if (
            args.max_new_batches is not None
            and generated_batches >= args.max_new_batches
        ):
            break
        if delay_seconds:
            print(f"provider pacing: waiting {delay_seconds:g}s", flush=True)
            time.sleep(delay_seconds)

    covered, row_count = inspect_shards(args.output_dir, len(contexts))
    expected_total = len(contexts) * 2
    if row_count != expected_total or len(covered) != len(contexts):
        if args.max_new_batches is not None:
            print(
                f"checkpointed partial dataset: {row_count}/{expected_total} goldens",
                flush=True,
            )
            return
        raise SystemExit(f"Expected {expected_total} total goldens, found {row_count}")
    print(
        f"validated complete sharded dataset: {row_count} goldens",
        flush=True,
    )


if __name__ == "__main__":
    main()
