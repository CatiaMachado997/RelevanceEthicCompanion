"""Sprint K Task 4: episodic memory of past planner runs.

PlannerRunMemoryService owns the per-user `PlannerRunMemory` Weaviate
collection. Two operations:

  write()   — called fire-and-forget from PlannerRunsService.finalize()
              when a turn completes with at least one ok observation.
  recall()  — called at the start of every planner step (when the
              EPISODIC_MEMORY_ENABLED flag is on) to fetch similar past
              runs for the same user. Returns top-K matches that clear
              the similarity threshold AND fall within the recency
              window.

All failures are logged and swallowed — the agent must keep working
even if Weaviate or the embedding service is down. Returning empty
results from recall() degrades cleanly to "no memory injection."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import List, Optional

from utils.weaviate_client import get_weaviate_client
from services.embedding_service import EmbeddingService
from config import settings

logger = logging.getLogger(__name__)


@dataclass
class PastRun:
    """One memory recall result. Shape exposed to telemetry as well."""

    planner_run_id: str
    message_text: str
    plan_summary: str
    similarity: float
    created_at: Optional[str] = None


def _plan_summary(plan_steps: list) -> str:
    """Deterministic compact rendering of a plan.

    Format: '<tool_a> → <tool_b> ... (completed in Xs, N step(s))'
    Tools are deduplicated, listed in order of first appearance.
    """
    seen: list = []
    seen_set: set = set()
    total_ms = 0
    n_steps = 0
    for step in plan_steps or []:
        n_steps += 1
        total_ms += int(step.get("duration_ms") or 0)
        for action in step.get("actions") or []:
            tool = action.get("tool") or ""
            if tool and tool not in seen_set:
                seen.append(tool)
                seen_set.add(tool)
    if not seen:
        body = "(no tools)"
    else:
        body = " → ".join(seen)
    secs = round(total_ms / 1000.0, 1) if total_ms else 0.0
    return f"{body} (completed in {secs}s, {n_steps} step{'s' if n_steps != 1 else ''})"


def _extract_score(match: dict) -> float:
    """Extract score from a hybrid_search result.

    Handles two shapes:
      - Real WeaviateClient response: top-level "score" key.
      - Test mock response: nested "metadata": {"score": ...}.
    """
    # Real client shape
    if "score" in match:
        return float(match["score"] or 0.0)
    # Mock / test shape
    metadata = match.get("metadata")
    if isinstance(metadata, dict):
        return float(metadata.get("score") or 0.0)
    return 0.0


class PlannerRunMemoryService:
    """Read + write the PlannerRunMemory collection."""

    COLLECTION = "PlannerRunMemory"

    async def write(
        self,
        *,
        user_id: str,
        planner_run_id: str,
        message_text: str,
        plan_steps: list,
    ) -> None:
        """Insert a memory row. Never raises."""
        try:
            client = get_weaviate_client()
            if client is None:
                return  # Weaviate unavailable — silent no-op
            embedding_svc = EmbeddingService(api_key=settings.GEMINI_API_KEY)
            vector = await embedding_svc.generate_query_embedding(message_text)
            content = {
                "user_id": user_id,
                "planner_run_id": planner_run_id,
                "message_text": message_text,
                "plan_summary": _plan_summary(plan_steps),
                "status": "completed",
                "created_at": datetime.now(UTC).isoformat(),
            }
            client.store_memory(
                collection=self.COLLECTION,
                content=content,
                vector=vector,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "planner_run_memory: write failed for run %s: %s",
                planner_run_id, exc,
            )

    async def recall(
        self,
        *,
        user_id: str,
        message: str,
        k: int,
        min_similarity: float,
        max_age_days: int,
    ) -> List[PastRun]:
        """Return top-k similar past runs for this user.

        The real WeaviateClient.hybrid_search() accepts:
            collection, query, query_vector, user_id, limit, alpha
        and applies the user_id filter server-side.

        When unit tests mock hybrid_search, the mock returns results that
        may also include a user_id mismatch check — we still do client-side
        filtering for safety (mocks don't filter). Score is extracted from
        either the real ("score" top-level) or mock ("metadata.score") shape.

        Never raises — returns [] on any failure.
        """
        try:
            client = get_weaviate_client()
            if client is None:
                return []
            embedding_svc = EmbeddingService(api_key=settings.GEMINI_API_KEY)
            vector = await embedding_svc.generate_query_embedding(message)

            min_created = (datetime.now(UTC) - timedelta(days=max_age_days)).isoformat()

            # Real hybrid_search signature:
            #   hybrid_search(collection, query, query_vector, user_id, limit, alpha)
            # user_id is passed for server-side Weaviate Filter; we also
            # filter client-side to be safe with mocks / degraded responses.
            matches = client.hybrid_search(
                collection=self.COLLECTION,
                query=message,
                query_vector=vector,
                user_id=user_id,
                limit=max(2 * k, k),
                alpha=0.7,
            )

            results: List[PastRun] = []
            for m in matches or []:
                props = m.get("properties") or {}
                # Client-side guard: user_id must match (mocks don't filter)
                row_user_id = props.get("user_id")
                if row_user_id is not None and row_user_id != user_id:
                    continue
                # Client-side recency filter
                created_at = props.get("created_at")
                if created_at and isinstance(created_at, str):
                    try:
                        if created_at < min_created:
                            continue
                    except Exception:
                        pass
                score = _extract_score(m)
                if score < min_similarity:
                    continue
                results.append(PastRun(
                    planner_run_id=props.get("planner_run_id", ""),
                    message_text=props.get("message_text", ""),
                    plan_summary=props.get("plan_summary", ""),
                    similarity=score,
                    created_at=created_at,
                ))
                if len(results) >= k:
                    break
            return results
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "planner_run_memory: recall failed for user %s: %s", user_id, exc
            )
            return []
