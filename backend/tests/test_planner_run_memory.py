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
    # Accept either kwarg or positional shape — both are reasonable.
    coll = call_args.kwargs.get("collection") or (call_args.args[0] if call_args.args else None)
    assert coll == "PlannerRunMemory"
    content = call_args.kwargs.get("content") or (call_args.args[1] if len(call_args.args) > 1 else None)
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
