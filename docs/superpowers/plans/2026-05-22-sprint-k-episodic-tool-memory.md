# Sprint K — Episodic Tool Memory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** At each planner step, fetch the top-3 most similar past completed runs for this user from a new Weaviate collection, format them as a brief SystemMessage, and prepend to the planner's input. Write the user's message + plan summary to the same collection (fire-and-forget) every time a turn completes successfully.

**Architecture:** New `PlannerRunMemory` Weaviate collection — schema added to `weaviate_config.py` so it's created on startup. New `PlannerRunMemoryService` with `write()` + `recall()`. `PlannerRunsService.finalize()` schedules the write via `asyncio.create_task` when status='completed' and ≥1 ok observation. `tool_planner_node` calls `recall()` at step start (gated on `EPISODIC_MEMORY_ENABLED`), prepends a SystemMessage with the matches, and folds `memory_used` into the first step's `tool_call_events.output`. Transparency tab renders "Drew on past plans" section when present.

**Tech Stack:** Python 3.13 · FastAPI · LangGraph 1.1.6 · Weaviate v4 (hybrid search, alpha=0.7) · Gemini text-embedding-004 · Next.js 16

**Branch:** `feat/sprint-k-episodic-memory` (already created; spec committed at `bbfb518`).

**Spec:** [`docs/superpowers/specs/2026-05-22-sprint-k-episodic-tool-memory-design.md`](../specs/2026-05-22-sprint-k-episodic-tool-memory-design.md)

---

## File map

| Path | Action | Purpose |
|---|---|---|
| `backend/config.py` | MODIFY | Four new settings (flag + three tuning knobs) |
| `backend/.env.example` | MODIFY | Document the four settings |
| `backend/weaviate_config.py` | MODIFY | Add `PlannerRunMemory` schema entry |
| `backend/services/planner_run_memory.py` | CREATE | `write()` + `recall()` + `_plan_summary()` helper |
| `backend/services/planner_runs.py` | MODIFY | `finalize()` schedules memory write on success |
| `backend/orchestrator/nodes/tools.py` | MODIFY | `tool_planner_node` calls `recall()`, prepends SystemMessage, folds `memory_used` into telemetry |
| `backend/tests/test_planner_run_memory.py` | CREATE | Service unit tests (write + recall + filtering) |
| `backend/tests/test_planner_memory_recall_integration.py` | CREATE | Integration test for SystemMessage injection |
| `frontend/components/transparency/ToolCallsTab.tsx` | MODIFY | Render "Drew on past plans" section when `output.memory_used` present |

10 files (4 new — 2 code, 2 test — and 5 modified, 1 frontend).

---

## Task 1 — Config + feature flag

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add four settings to `Settings` class in `backend/config.py`**

Add after the existing `STREAMING_REASONING_ENABLED` line:

```python
    # Sprint K — episodic tool memory. When False (default), no
    # PlannerRunMemory writes, no recall queries, no prompt augmentation.
    # When True, the planner gets a short SystemMessage at the start of
    # every step listing the top-K most similar past completed runs.
    EPISODIC_MEMORY_ENABLED: bool = False
    # Max past runs returned per recall.
    EPISODIC_MEMORY_TOP_K: int = 3
    # Hybrid-score floor for a match to make the cut.
    EPISODIC_MEMORY_MIN_SIMILARITY: float = 0.6
    # Recency window: ignore matches older than this many days.
    EPISODIC_MEMORY_MAX_AGE_DAYS: int = 90
```

- [ ] **Step 2: Document the four in `.env.example`**

Add after the existing `STREAMING_REASONING_ENABLED` line:

```
# Sprint K — episodic tool memory. Default off; flip on once smoke-tested
# in staging. The three tuning knobs are env-configurable so we can adjust
# without redeploying code.
EPISODIC_MEMORY_ENABLED=false
EPISODIC_MEMORY_TOP_K=3
EPISODIC_MEMORY_MIN_SIMILARITY=0.6
EPISODIC_MEMORY_MAX_AGE_DAYS=90
```

- [ ] **Step 3: Verify the settings load**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09/backend
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -c "
from config import settings
print('flag:', settings.EPISODIC_MEMORY_ENABLED)
print('top_k:', settings.EPISODIC_MEMORY_TOP_K)
print('min_sim:', settings.EPISODIC_MEMORY_MIN_SIMILARITY)
print('max_age:', settings.EPISODIC_MEMORY_MAX_AGE_DAYS)
"
```
Expected: `flag: False / top_k: 3 / min_sim: 0.6 / max_age: 90`.

- [ ] **Step 4: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09
git add backend/config.py backend/.env.example
git commit -m "Sprint K Task 1: EPISODIC_MEMORY_* feature flag + tuning knobs"
```

---

## Task 2 — `PlannerRunMemory` Weaviate schema

**Files:**
- Modify: `backend/weaviate_config.py`

- [ ] **Step 1: Append the schema to `WEAVIATE_SCHEMAS`**

Add this entry as a new item in the `WEAVIATE_SCHEMAS` list (after the `DocumentMemory` entry, just before the closing `]`):

```python
    {
        "class": "PlannerRunMemory",
        "description": "Per-user record of past completed planner runs, "
                       "embedded for similarity recall at planner-step start. "
                       "Sprint K.",
        "vectorizer": "none",
        "properties": [
            {
                "name": "user_id",
                "dataType": ["text"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "planner_run_id",
                "dataType": ["text"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "message_text",
                "dataType": ["text"],
                "indexFilterable": False,
                "indexSearchable": True,
            },
            {
                "name": "plan_summary",
                "dataType": ["text"],
                "indexFilterable": False,
                "indexSearchable": False,
            },
            {
                "name": "status",
                "dataType": ["text"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "created_at",
                "dataType": ["date"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
        ],
    },
```

- [ ] **Step 2: Verify the config parses**

```bash
cd backend
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -c "
from weaviate_config import WEAVIATE_SCHEMAS, get_collection_schema
print('count:', len(WEAVIATE_SCHEMAS))
schema = get_collection_schema('PlannerRunMemory')
print('class:', schema['class'])
print('props:', [p['name'] for p in schema['properties']])
"
```
Expected: `count: 5` (was 4); `class: PlannerRunMemory`; props list shows all six.

Collection creation happens via `WeaviateClient.initialize_schemas()` on backend startup (it iterates `WEAVIATE_SCHEMAS` and creates any that don't exist). No separate migration step required.

- [ ] **Step 3: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09
git add backend/weaviate_config.py
git commit -m "Sprint K Task 2: add PlannerRunMemory Weaviate schema"
```

---

## Task 3 — `PlannerRunMemoryService` failing tests (write + recall)

**Files:**
- Test: `backend/tests/test_planner_run_memory.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_planner_run_memory.py`:

```python
"""Sprint K Task 3: unit tests for PlannerRunMemoryService."""

from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.planner_run_memory import (
    PlannerRunMemoryService,
    PastRun,
    _plan_summary,
)


USER_ID = "00000000-0000-0000-0000-000000000000"


# ─── _plan_summary helper ────────────────────────────────────────


def test_plan_summary_single_step_single_action():
    """One step with one ok action → 'tool_name (completed in Xs, 1 step)'."""
    plan_steps = [{
        "step": 1, "thought": "x",
        "actions": [{"tool": "query_calendar", "params": {}}],
        "observations": [{"status": "ok", "latency_ms": 410, "attempts": 1}],
        "duration_ms": 412,
    }]
    s = _plan_summary(plan_steps)
    assert "query_calendar" in s
    assert "1 step" in s


def test_plan_summary_multi_step_multi_action():
    """Two tools across two steps → 'tool_a → tool_b ...'."""
    plan_steps = [
        {
            "step": 1, "thought": "x",
            "actions": [{"tool": "search_documents", "params": {}}],
            "observations": [{"status": "ok", "latency_ms": 1000}],
            "duration_ms": 1000,
        },
        {
            "step": 2, "thought": "y",
            "actions": [{"tool": "query_calendar", "params": {}}],
            "observations": [{"status": "ok", "latency_ms": 200}],
            "duration_ms": 200,
        },
    ]
    s = _plan_summary(plan_steps)
    assert "search_documents" in s
    assert "query_calendar" in s
    assert "→" in s
    assert "2 step" in s


def test_plan_summary_deduplicates_repeated_tools():
    """If the same tool runs twice, it appears once in the summary."""
    plan_steps = [{
        "step": 1, "thought": "x",
        "actions": [
            {"tool": "search_documents", "params": {"q": "a"}},
            {"tool": "search_documents", "params": {"q": "b"}},
        ],
        "observations": [
            {"status": "ok", "latency_ms": 100},
            {"status": "ok", "latency_ms": 120},
        ],
        "duration_ms": 220,
    }]
    s = _plan_summary(plan_steps)
    # search_documents should appear exactly once
    assert s.count("search_documents") == 1


# ─── write() ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_inserts_with_embedding():
    """write() embeds the message and inserts a Weaviate object."""
    fake_client = MagicMock()
    fake_embedding_svc = MagicMock()
    fake_embedding_svc.generate_query_embedding = AsyncMock(return_value=[0.1] * 768)

    with patch(
        "services.planner_run_memory.get_weaviate_client", return_value=fake_client
    ), patch(
        "services.planner_run_memory.EmbeddingService", return_value=fake_embedding_svc
    ):
        svc = PlannerRunMemoryService()
        await svc.write(
            user_id=USER_ID,
            planner_run_id="run-1",
            message_text="what was the M-KOPA email?",
            plan_steps=[{
                "step": 1, "thought": "x",
                "actions": [{"tool": "search_documents", "params": {}}],
                "observations": [{"status": "ok", "latency_ms": 100}],
                "duration_ms": 100,
            }],
        )

    fake_embedding_svc.generate_query_embedding.assert_called_once()
    fake_client.store_memory.assert_called_once()
    call_args = fake_client.store_memory.call_args
    assert call_args.kwargs.get("collection") == "PlannerRunMemory" or call_args.args[0] == "PlannerRunMemory"
    content = call_args.kwargs.get("content") or call_args.args[1]
    assert content["user_id"] == USER_ID
    assert content["planner_run_id"] == "run-1"
    assert content["message_text"] == "what was the M-KOPA email?"
    assert "search_documents" in content["plan_summary"]
    assert content["status"] == "completed"


@pytest.mark.asyncio
async def test_write_swallows_errors():
    """A failure inside write() must never propagate — turn flow can't break."""
    fake_embedding_svc = MagicMock()
    fake_embedding_svc.generate_query_embedding = AsyncMock(
        side_effect=RuntimeError("embedding API down")
    )
    with patch(
        "services.planner_run_memory.get_weaviate_client", return_value=MagicMock()
    ), patch(
        "services.planner_run_memory.EmbeddingService", return_value=fake_embedding_svc
    ):
        svc = PlannerRunMemoryService()
        # Must not raise
        await svc.write(
            user_id=USER_ID,
            planner_run_id="run-2",
            message_text="x",
            plan_steps=[{"step": 1, "thought": "x", "actions": [],
                        "observations": [], "duration_ms": 0}],
        )


@pytest.mark.asyncio
async def test_write_no_client_no_op():
    """If Weaviate client is None (unavailable), write() returns silently."""
    with patch("services.planner_run_memory.get_weaviate_client", return_value=None):
        svc = PlannerRunMemoryService()
        await svc.write(
            user_id=USER_ID, planner_run_id="r",
            message_text="x", plan_steps=[],
        )  # no raise


# ─── recall() ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recall_returns_empty_on_no_matches():
    fake_client = MagicMock()
    fake_client.hybrid_search = MagicMock(return_value=[])
    fake_embedding_svc = MagicMock()
    fake_embedding_svc.generate_query_embedding = AsyncMock(return_value=[0.1] * 768)

    with patch(
        "services.planner_run_memory.get_weaviate_client", return_value=fake_client
    ), patch(
        "services.planner_run_memory.EmbeddingService", return_value=fake_embedding_svc
    ):
        svc = PlannerRunMemoryService()
        result = await svc.recall(
            user_id=USER_ID, message="hi", k=3,
            min_similarity=0.6, max_age_days=90,
        )
    assert result == []


@pytest.mark.asyncio
async def test_recall_filters_below_threshold():
    """Matches with score < min_similarity are dropped."""
    now_iso = datetime.now(UTC).isoformat()
    fake_client = MagicMock()
    fake_client.hybrid_search = MagicMock(return_value=[
        {
            "properties": {
                "planner_run_id": "high", "message_text": "a",
                "plan_summary": "s1", "created_at": now_iso,
            },
            "metadata": {"score": 0.85},
        },
        {
            "properties": {
                "planner_run_id": "low", "message_text": "b",
                "plan_summary": "s2", "created_at": now_iso,
            },
            "metadata": {"score": 0.40},
        },
    ])
    fake_embedding_svc = MagicMock()
    fake_embedding_svc.generate_query_embedding = AsyncMock(return_value=[0.1] * 768)

    with patch(
        "services.planner_run_memory.get_weaviate_client", return_value=fake_client
    ), patch(
        "services.planner_run_memory.EmbeddingService", return_value=fake_embedding_svc
    ):
        svc = PlannerRunMemoryService()
        result = await svc.recall(
            user_id=USER_ID, message="similar?", k=3,
            min_similarity=0.6, max_age_days=90,
        )
    ids = [r.planner_run_id for r in result]
    assert ids == ["high"]  # 'low' dropped by threshold


@pytest.mark.asyncio
async def test_recall_respects_top_k():
    """If more matches than k pass the threshold, only k are returned."""
    now_iso = datetime.now(UTC).isoformat()
    matches = [
        {
            "properties": {
                "planner_run_id": f"r{i}",
                "message_text": "x",
                "plan_summary": "s",
                "created_at": now_iso,
            },
            "metadata": {"score": 0.9 - i * 0.01},
        }
        for i in range(5)
    ]
    fake_client = MagicMock()
    fake_client.hybrid_search = MagicMock(return_value=matches)
    fake_embedding_svc = MagicMock()
    fake_embedding_svc.generate_query_embedding = AsyncMock(return_value=[0.1] * 768)

    with patch(
        "services.planner_run_memory.get_weaviate_client", return_value=fake_client
    ), patch(
        "services.planner_run_memory.EmbeddingService", return_value=fake_embedding_svc
    ):
        svc = PlannerRunMemoryService()
        result = await svc.recall(
            user_id=USER_ID, message="x", k=2,
            min_similarity=0.0, max_age_days=90,
        )
    assert len(result) == 2
    assert [r.planner_run_id for r in result] == ["r0", "r1"]


@pytest.mark.asyncio
async def test_recall_swallows_errors():
    """A failure inside recall() returns empty (planner proceeds without memory)."""
    fake_embedding_svc = MagicMock()
    fake_embedding_svc.generate_query_embedding = AsyncMock(
        side_effect=RuntimeError("embedding down")
    )
    with patch(
        "services.planner_run_memory.get_weaviate_client", return_value=MagicMock()
    ), patch(
        "services.planner_run_memory.EmbeddingService", return_value=fake_embedding_svc
    ):
        svc = PlannerRunMemoryService()
        result = await svc.recall(
            user_id=USER_ID, message="x", k=3,
            min_similarity=0.6, max_age_days=90,
        )
    assert result == []
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd backend
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/pytest tests/test_planner_run_memory.py -v
```
Expected: `ModuleNotFoundError: No module named 'services.planner_run_memory'`.

- [ ] **Step 3: Commit (test-first)**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09
git add backend/tests/test_planner_run_memory.py
git commit -m "Sprint K Task 3 (test-first): PlannerRunMemoryService unit tests"
```

---

## Task 4 — `PlannerRunMemoryService` implementation

**Files:**
- Create: `backend/services/planner_run_memory.py`

- [ ] **Step 1: Write the service**

```python
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
                planner_run_id,
                exc,
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

        Filters: user_id (exact), created_at within max_age_days,
        hybrid_score >= min_similarity.
        Never raises — returns [] on any failure.
        """
        try:
            client = get_weaviate_client()
            if client is None:
                return []
            embedding_svc = EmbeddingService(api_key=settings.GEMINI_API_KEY)
            vector = await embedding_svc.generate_query_embedding(message)

            min_created = (datetime.now(UTC) - timedelta(days=max_age_days)).isoformat()
            # hybrid_search returns a list of {properties, metadata} dicts;
            # the metadata.score is the Weaviate hybrid relevance score.
            # We request a buffer of 2*k matches and then re-filter, in case
            # several drop below the threshold.
            matches = client.hybrid_search(
                collection=self.COLLECTION,
                query=message,
                vector=vector,
                alpha=0.7,
                limit=max(2 * k, k),
                where_filters={
                    "user_id": user_id,
                    "created_at_gte": min_created,
                },
            )
            results: List[PastRun] = []
            for m in matches or []:
                score = float((m.get("metadata") or {}).get("score") or 0.0)
                if score < min_similarity:
                    continue
                props = m.get("properties") or {}
                results.append(PastRun(
                    planner_run_id=props.get("planner_run_id", ""),
                    message_text=props.get("message_text", ""),
                    plan_summary=props.get("plan_summary", ""),
                    similarity=score,
                    created_at=props.get("created_at"),
                ))
                if len(results) >= k:
                    break
            return results
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "planner_run_memory: recall failed for user %s: %s", user_id, exc
            )
            return []
```

**Note for the implementer:** `WeaviateClient.hybrid_search` (in `backend/utils/weaviate_client.py`) is the existing method used by RAG retrieval — its exact signature (especially the `where_filters` shape) determines what kwargs to pass. **Read that function first.** If the signature differs from what I've written here, adapt the kwargs in `recall()` to match. The contract that matters: filter by `user_id` and a `created_at` lower bound, return objects ordered by hybrid score descending. If `where_filters` isn't supported on `hybrid_search`, do the filtering client-side after the call returns.

- [ ] **Step 2: Run tests**

```bash
cd backend
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/pytest tests/test_planner_run_memory.py -v
```
Expected: all 9 tests pass.

If `hybrid_search`'s `where_filters` kwarg doesn't exist, the test mocks the method anyway (they patch the client directly) — so the tests will pass even if you adapted the kwarg in `recall()`. **But verify** the real signature aligns with what the implementation actually calls; the integration test in Task 9 exercises the real path.

- [ ] **Step 3: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09
git add backend/services/planner_run_memory.py
git commit -m "Sprint K Task 4: PlannerRunMemoryService — write + recall + plan summary"
```

---

## Task 5 — Hook `PlannerRunsService.finalize()` to schedule memory write

**Files:**
- Modify: `backend/services/planner_runs.py`

- [ ] **Step 1: Add the eligibility check + async schedule**

Open `backend/services/planner_runs.py`. Locate the `finalize()` method (around line 65). At the END of the method, AFTER the UPDATE statement and the outer `try/except`, add the following block. The behavior we want: only schedule when status='completed' AND at least one observation across all steps has status='ok'. Schedule a fire-and-forget asyncio task.

Replace this block at the end of `finalize()`:

```python
        except Exception as exc:  # noqa: BLE001 — telemetry must not raise
            logger.warning(
                "planner_runs: finalize failed for run %s: %s", run_id, exc
            )
```

…with this expanded version that adds the memory-write scheduling:

```python
        except Exception as exc:  # noqa: BLE001 — telemetry must not raise
            logger.warning(
                "planner_runs: finalize failed for run %s: %s", run_id, exc
            )
            return

        # Sprint K — schedule a fire-and-forget memory write if this run
        # is worth remembering. Eligibility: status='completed' AND at
        # least one action observation has status='ok'.
        if not _settings.EPISODIC_MEMORY_ENABLED:
            return
        if status != "completed":
            return
        has_ok = any(
            (obs or {}).get("status") == "ok"
            for step in (plan_steps or [])
            for obs in (step.get("observations") or [])
        )
        if not has_ok:
            return
        # Reconstruct the user_id + message_text from the run row.
        # We don't have them on hand in finalize() (the args don't carry
        # them); fetch them in a tiny SELECT.
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT pr.user_id, ct.content AS message_text
                             FROM planner_runs pr
                        LEFT JOIN conversation_turns ct
                               ON ct.id = pr.conversation_turn_id
                            WHERE pr.id = %s""",
                        (run_id,),
                    )
                    row = cur.fetchone() or {}
            user_id = row.get("user_id")
            message_text = row.get("message_text") or ""
            if not user_id or not message_text:
                return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "planner_run_memory: finalize lookup failed for %s: %s",
                run_id, exc,
            )
            return
        try:
            import asyncio
            from services.planner_run_memory import PlannerRunMemoryService

            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    PlannerRunMemoryService().write(
                        user_id=str(user_id),
                        planner_run_id=run_id,
                        message_text=message_text,
                        plan_steps=plan_steps,
                    )
                )
            # If there is no running loop (e.g. tests calling finalize
            # synchronously), silently skip — the test won't be exercising
            # the memory write path anyway.
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "planner_run_memory: schedule failed for %s: %s", run_id, exc
            )
```

Then, near the top of `backend/services/planner_runs.py`, add the settings import (aliased to avoid shadowing):

```python
from config import settings as _settings
```

**Important:** the `conversation_turn_id` join in the SELECT depends on Sprint I writing that FK. If `conversation_turn_id` is NULL on the row, the LEFT JOIN returns no `message_text`, and the `if not user_id or not message_text:` guard short-circuits with no write. Acceptable degradation; we can backfill later if needed.

- [ ] **Step 2: Verify the existing planner_runs tests still pass**

```bash
cd backend
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/pytest tests/test_planner_runs_service.py -v
```
Expected: all 5 tests pass. (The new branch is gated on the flag being True; defaults are False so existing tests don't exercise it.)

- [ ] **Step 3: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09
git add backend/services/planner_runs.py
git commit -m "Sprint K Task 5: finalize() schedules fire-and-forget memory write"
```

---

## Task 6 — Failing integration test for SystemMessage injection

**Files:**
- Test: `backend/tests/test_planner_memory_recall_integration.py`

- [ ] **Step 1: Write the failing test**

```python
"""Sprint K Task 6: integration test — tool_planner_node prepends a
SystemMessage when PlannerRunMemoryService.recall() returns matches."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.state import AgentState
from orchestrator.nodes.tools import tool_planner_node
from services.planner_run_memory import PastRun


USER_ID = "00000000-0000-0000-0000-000000000000"


def _base_state() -> AgentState:
    state: AgentState = {
        "user_id": USER_ID,
        "message": "what's on my calendar this week?",
        "conversation_id": "c-1",
        "model": "llama-3.3-70b-versatile",
        "user_context": {},
        "conversation_history": [],
        "active_sources": [],
        "intent": "chat",
        "tool_calls": [],
        "tool_results": [],
        "esl_decision": None,
        "proposed_content": "",
        "response_text": "",
        "response_events": [],
        "citations": [],
        "document_sources": [],
        "token_count": 0,
        "token_warning": None,
        "pending_tool_confirmation": None,
        "source_context": [],
        "force_retrieval": False,
        "planner_step": 0,
        "max_planner_steps": 3,
        "plan_steps": [],
        "planner_run_id": None,
    }
    return state


def _mk_planner_llm():
    """Mock LLM that returns a response with no tool calls (terminal step)."""
    inner = MagicMock()
    resp = MagicMock()
    resp.content = "I have enough."
    resp.tool_calls = []
    inner.ainvoke = AsyncMock(return_value=resp)
    inner.bind_tools = MagicMock(return_value=inner)
    return MagicMock(return_value=inner)


@pytest.mark.asyncio
async def test_planner_prepends_memory_system_message_when_recall_hits():
    """When EPISODIC_MEMORY_ENABLED and recall returns matches, the planner
    LLM is invoked with a SystemMessage whose content includes the past
    plan summaries."""
    fake_past = [
        PastRun(
            planner_run_id="run-a",
            message_text="what was on my calendar last week",
            plan_summary="query_calendar (completed in 0.4s, 1 step)",
            similarity=0.81,
        ),
    ]

    captured_messages: list = []

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        resp = MagicMock()
        resp.content = "I have enough."
        resp.tool_calls = []
        return resp

    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = fake_ainvoke

    with patch("orchestrator.nodes.tools._j_settings") as flag, \
         patch("orchestrator.nodes.tools.get_context_manager",
               MagicMock(return_value=MagicMock())), \
         patch("services.langchain_tools.create_langchain_tools",
               AsyncMock(return_value=[])), \
         patch("orchestrator.nodes.tools.PlannerRunMemoryService") as MemCls, \
         patch("services.planner_runs.PlannerRunsService") as RunsCls, \
         patch("langchain_groq.ChatGroq", return_value=llm):
        flag.STREAMING_REASONING_ENABLED = False  # streaming events off
        flag.EPISODIC_MEMORY_ENABLED = True
        flag.EPISODIC_MEMORY_TOP_K = 3
        flag.EPISODIC_MEMORY_MIN_SIMILARITY = 0.6
        flag.EPISODIC_MEMORY_MAX_AGE_DAYS = 90
        MemCls.return_value.recall = AsyncMock(return_value=fake_past)
        RunsCls.return_value.create = MagicMock(return_value="run-new")

        result = await tool_planner_node(_base_state())

    # A SystemMessage with the memory content should have been added.
    contents = [getattr(m, "content", "") for m in captured_messages]
    assert any(
        "handled similar questions" in (c or "").lower()
        for c in contents
    ), f"missing memory SystemMessage; saw: {contents[:3]}"
    assert any("query_calendar" in (c or "") for c in contents)

    # The first plan step's telemetry should carry memory_used.
    ps = result.get("plan_steps") or []
    assert ps, "plan_steps missing"
    first = ps[0]
    assert "memory_used" in first or "memory_used" in (first.get("metadata") or {}), \
        f"memory_used not folded into step; first step: {first}"


@pytest.mark.asyncio
async def test_planner_skips_memory_when_flag_off():
    """When EPISODIC_MEMORY_ENABLED is False, recall is not called and no
    SystemMessage is prepended."""
    captured_messages: list = []

    async def fake_ainvoke(messages):
        captured_messages.extend(messages)
        resp = MagicMock()
        resp.content = "ok"
        resp.tool_calls = []
        return resp

    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = fake_ainvoke

    mem_cls = MagicMock()
    mem_cls.return_value.recall = AsyncMock(return_value=[])

    with patch("orchestrator.nodes.tools._j_settings") as flag, \
         patch("orchestrator.nodes.tools.get_context_manager",
               MagicMock(return_value=MagicMock())), \
         patch("services.langchain_tools.create_langchain_tools",
               AsyncMock(return_value=[])), \
         patch("orchestrator.nodes.tools.PlannerRunMemoryService", mem_cls), \
         patch("services.planner_runs.PlannerRunsService") as RunsCls, \
         patch("langchain_groq.ChatGroq", return_value=llm):
        flag.STREAMING_REASONING_ENABLED = False
        flag.EPISODIC_MEMORY_ENABLED = False  # OFF
        flag.EPISODIC_MEMORY_TOP_K = 3
        flag.EPISODIC_MEMORY_MIN_SIMILARITY = 0.6
        flag.EPISODIC_MEMORY_MAX_AGE_DAYS = 90
        RunsCls.return_value.create = MagicMock(return_value="run-new")

        await tool_planner_node(_base_state())

    mem_cls.return_value.recall.assert_not_called()
    contents = [getattr(m, "content", "") for m in captured_messages]
    assert not any(
        "handled similar questions" in (c or "").lower() for c in contents
    )
```

- [ ] **Step 2: Run, verify it fails**

```bash
cd backend
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/pytest tests/test_planner_memory_recall_integration.py -v
```
Expected: failures — the planner node doesn't yet call `PlannerRunMemoryService` and doesn't prepend a SystemMessage.

- [ ] **Step 3: Commit (test-first)**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09
git add backend/tests/test_planner_memory_recall_integration.py
git commit -m "Sprint K Task 6 (test-first): planner-node memory injection integration test"
```

---

## Task 7 — Wire `tool_planner_node` to call `recall()` and prepend SystemMessage

**Files:**
- Modify: `backend/orchestrator/nodes/tools.py`

- [ ] **Step 1: Add the import**

Near the top of `backend/orchestrator/nodes/tools.py`, alongside the existing Sprint J imports (`from services.safety_preferences import ...`), add:

```python
from services.planner_run_memory import PlannerRunMemoryService
```

- [ ] **Step 2: Inject memory at planner-step start**

Inside `tool_planner_node`, find the place where messages are built — right after the existing block that appends the conversation history and the latest user message, AND right before the LLM invocation (`response = await llm_with_tools.ainvoke(messages)`).

This block is gated on `_j_settings.EPISODIC_MEMORY_ENABLED` AND fires only on the first step (`len(plan_steps) == 0`) — we don't want to inject memory at every replan iteration; the memory exists to bias the initial plan, not to nag at every step.

Insert this block right before `response = await llm_with_tools.ainvoke(messages)`:

```python
    # Sprint K — episodic memory: on the FIRST planner step of the turn,
    # consult past completed runs for this user and prepend a brief
    # SystemMessage with the matches. The LLM retains full agency.
    memory_used: list = []
    if (
        _j_settings.EPISODIC_MEMORY_ENABLED
        and len(plan_steps) == 0  # first step only
    ):
        try:
            past_runs = await PlannerRunMemoryService().recall(
                user_id=user_id,
                message=state["message"],
                k=_j_settings.EPISODIC_MEMORY_TOP_K,
                min_similarity=_j_settings.EPISODIC_MEMORY_MIN_SIMILARITY,
                max_age_days=_j_settings.EPISODIC_MEMORY_MAX_AGE_DAYS,
            )
        except Exception as exc:  # defense-in-depth — recall already swallows
            logger.warning("episodic memory recall failed: %s", exc)
            past_runs = []
        if past_runs:
            memory_used = [
                {
                    "planner_run_id": r.planner_run_id,
                    "message_text": r.message_text,
                    "plan_summary": r.plan_summary,
                    "similarity": r.similarity,
                }
                for r in past_runs
            ]
            lines = [
                f'- "{r.message_text}" → {r.plan_summary}'
                for r in past_runs
            ]
            mem_block = (
                "You've handled similar questions before. Past examples "
                "(most recent first, may be stale):\n"
                + "\n".join(lines)
                + "\n\nUse these as hints, not rules — the current question "
                "may need a different plan."
            )
            messages.insert(0, SystemMessage(content=mem_block))
```

Note: `SystemMessage` is already imported inside `tool_planner_node` from `langchain_core.messages` (read the function to confirm — if not, hoist that import or add it). `logger` is module-level.

- [ ] **Step 3: Fold `memory_used` into the step's record**

When the planner step's dict is appended to `plan_steps` (find the existing dict literal that has `"step": ..., "thought": ..., "actions": ..., "observations": []`), tack on a `memory_used` key:

```python
    step = {
        "step": next_step_index,
        "thought": parsed["thought"],
        "actions": parsed["actions"],
        "observations": [],
        "started_at": datetime.now(UTC).isoformat(),
        "memory_used": memory_used,  # Sprint K — empty list on non-first or flag-off
    }
```

This makes the recall result visible in `plan_steps[0]["memory_used"]` which becomes part of `tool_call_events.output` via the executor's existing telemetry path (no executor change required — the telemetry function already serializes the full step).

- [ ] **Step 4: Run the integration test from Task 6**

```bash
cd backend
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/pytest tests/test_planner_memory_recall_integration.py -v
```
Expected: both tests pass.

The first test's final assertion (`assert "memory_used" in first ...`) checks the field is present on the step dict. The second test asserts `recall.assert_not_called()` — verifying the early `if not _j_settings.EPISODIC_MEMORY_ENABLED: return` short-circuit works.

- [ ] **Step 5: Run the full Sprint K test set**

```bash
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/pytest tests/test_planner_run_memory.py tests/test_planner_memory_recall_integration.py tests/test_planner_runs_service.py -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09
git add backend/orchestrator/nodes/tools.py
git commit -m "Sprint K Task 7: planner_node calls recall() and prepends memory SystemMessage"
```

---

## Task 8 — Run full backend suite + fix any regressions

**Files:** none — verification only.

- [ ] **Step 1: Run the full backend suite**

```bash
cd backend
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/pytest --tb=short -q
```
Expected: 489+ passed (482 baseline + ~7 new tests from Sprint K), 2 skipped, 0 failed.

If any pre-existing tests now fail, they're most likely existing planner-loop tests that no longer patch the new dependency `PlannerRunMemoryService` or `_settings.EPISODIC_MEMORY_*`. Diagnose and patch the test fixtures — DO NOT change the implementation to work around a fixture gap unless the change is also correct production behavior.

- [ ] **Step 2: If any fixes needed, commit them**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09
git add <whatever-test-files-needed-patching>
git commit -m "Sprint K Task 8: tighten test fixtures for new planner dependencies"
```

If no fixes needed, skip the commit.

---

## Task 9 — Frontend Transparency: "Drew on past plans" section

**Files:**
- Modify: `frontend/components/transparency/ToolCallsTab.tsx`

- [ ] **Step 1: Read the existing component first**

The Sprint I detail-dialog already renders a "Retrieval trace" section when `output.trace` is present (Sprint G). Add a parallel section when `output.memory_used` is present — same visual idiom (a small bordered card inside the detail dialog).

- [ ] **Step 2: Add the rendering logic**

Inside the detail dialog (the section that branches on `event.tool_name === "search_documents"` or similar), add a new conditional block. Approximate shape:

```tsx
{Array.isArray(output?.memory_used) && output.memory_used.length > 0 && (
  <div className="rounded-lg p-3 mt-3"
    style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}>
    <div className="text-xs font-medium mb-2" style={{ color: 'var(--ec-text)' }}>
      Drew on past plans
    </div>
    <ul className="space-y-1.5">
      {output.memory_used.map((m: any, i: number) => (
        <li key={m.planner_run_id ?? i} className="text-xs">
          <div style={{ color: 'var(--ec-text)' }}>
            "{m.message_text}"
          </div>
          <div style={{ color: 'var(--ec-text-muted)' }}>
            {m.plan_summary}
            {typeof m.similarity === 'number' && (
              <span className="ml-2" style={{ color: 'var(--ec-text-subtle)' }}>
                · similarity {m.similarity.toFixed(2)}
              </span>
            )}
          </div>
        </li>
      ))}
    </ul>
  </div>
)}
```

Place this near the existing Retrieval-trace section (or near the existing per-event detail body — wherever the detail dialog's body lives in the file). The exact placement is up to the implementer; the visual contract is "a small bordered card with a heading and a list of past runs."

The `memory_used` field lives on the FIRST tool_planner step inside `plan_steps[0]` of `output` — depending on how the existing code accesses `output`, you may need to drill into `output.plan_steps?.[0]?.memory_used` instead of `output.memory_used`. Check the existing Retrieval-trace logic for the analogous access pattern (it reads `output.trace`, which lives wherever the search_documents tool puts it).

- [ ] **Step 3: Typecheck**

```bash
cd frontend
npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09
git add frontend/components/transparency/ToolCallsTab.tsx
git commit -m "Sprint K Task 9: render 'Drew on past plans' section when memory_used present"
```

---

## Task 10 — Push, PR, manual smoke

**Files:** none — wrap-up.

- [ ] **Step 1: Push the branch**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/.claude/worktrees/pensive-jemison-645b09
git push -u origin feat/sprint-k-episodic-memory
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --title "Sprint K — Episodic tool memory" --body "$(cat <<'EOF'
Implements docs/superpowers/specs/2026-05-22-sprint-k-episodic-tool-memory-design.md.

## What changed
- New Weaviate collection `PlannerRunMemory` (per-user, partitioned by user_id property).
- New `PlannerRunMemoryService` with `write()` + `recall()` + a deterministic `_plan_summary()` helper.
- `PlannerRunsService.finalize()` schedules a fire-and-forget memory write via asyncio.create_task when status='completed' AND ≥1 ok observation.
- `tool_planner_node` consults recall() at the first step of every turn (gated on EPISODIC_MEMORY_ENABLED) and prepends a brief SystemMessage with the top-K matches.
- `memory_used` array folded into the first step's tool_call_events.output; Transparency tab renders a "Drew on past plans" section.
- All behind EPISODIC_MEMORY_ENABLED feature flag (default off); three tuning knobs (top_k, min_similarity, max_age_days) all env-configurable.

## Verification
- [x] Backend `pytest --tb=short -q` passes
- [x] Frontend `npx tsc --noEmit` clean
- [x] Tests: 9 unit (PlannerRunMemoryService) + 2 integration (planner-node SystemMessage injection)
- [x] No state changes to AgentState — recall is local to tool_planner_node

## Rollout
1. Merge with EPISODIC_MEMORY_ENABLED=false.
2. Enable in staging; seed ~10 conversations; verify recall in Transparency.
3. Tune top_k / min_similarity / max_age_days if needed.
4. Flip in prod.
5. Remove flag after one stable week.

Closes the I → J → K agent-integration deepening track.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Manual smoke (in staging once the flag is on)**

1. Run one turn with a knowledge-recall question ("what's on my calendar today"). Wait for completion. Confirm a `PlannerRunMemory` object exists for the user.
2. Run another turn with a similar question. In Transparency tab, click the first `tool_planner` event for that turn. Expected: "Drew on past plans" section listing the previous run with similarity ≥ 0.6.
3. Run an unrelated turn ("translate 'hello' to French"). Expected: no memory_used or empty.
4. Restart the backend mid-deploy. Confirm `PlannerRunMemory` rows persist (Weaviate is durable) and recall keeps working.

---

## Self-review

Spec coverage:

| Spec section | Task(s) |
|---|---|
| Goal 1 (persist per-turn embeddings) | Tasks 2, 4, 5 |
| Goal 2 (recall at planner-step start) | Tasks 4, 7 |
| Goal 3 (prompt augmentation) | Task 7 |
| Goal 4 (Transparency surface) | Tasks 7 (telemetry fold), 9 (UI) |
| Goal 5 (no latency penalty on visible path) | Task 5 (asyncio.create_task) |
| Eligibility filter (completed + ≥1 ok) | Task 5 |
| Weaviate collection schema | Task 2 |
| Configuration (flag + 3 knobs) | Task 1 |
| Tests (unit + integration) | Tasks 3, 6 |
| Failure handling (recall/write never raise) | Task 4 |

No placeholders found. Method signatures (`PlannerRunMemoryService.write(*, user_id, planner_run_id, message_text, plan_steps)`, `.recall(*, user_id, message, k, min_similarity, max_age_days)`, `_plan_summary(plan_steps) -> str`, dataclass `PastRun(planner_run_id, message_text, plan_summary, similarity, created_at)`) consistent across Tasks 3, 4, 6, 7. File paths exact. Code blocks complete in every code-change step.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-22-sprint-k-episodic-tool-memory.md`.**
