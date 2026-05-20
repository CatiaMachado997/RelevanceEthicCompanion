"""Sprint I Task 8: unit tests for _execute_with_retry helper."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.nodes.tools import _execute_with_retry


def _fake_tool(name: str, side_effect):
    t = MagicMock()
    t.name = name
    t.ainvoke = AsyncMock(side_effect=side_effect)
    return t


@pytest.mark.asyncio
async def test_succeeds_on_first_try():
    t = _fake_tool("query_calendar", side_effect=[{"events": [1, 2]}])
    obs = await _execute_with_retry(t, {"days": 7})
    assert obs["status"] == "ok"
    assert obs["result"] == {"events": [1, 2]}
    assert obs["attempts"] == 1
    assert obs["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_succeeds_on_retry():
    """First call raises, second call returns. Net: ok with attempts=2."""
    t = _fake_tool("web_search", side_effect=[RuntimeError("transient"), "result"])
    obs = await _execute_with_retry(t, {"q": "x"})
    assert obs["status"] == "ok"
    assert obs["result"] == "result"
    assert obs["attempts"] == 2


@pytest.mark.asyncio
async def test_fails_both_attempts_returns_error_observation():
    """Two raises → status='error', error message captured, never re-raises."""
    t = _fake_tool(
        "web_search", side_effect=[RuntimeError("first"), RuntimeError("second")]
    )
    obs = await _execute_with_retry(t, {"q": "x"})
    assert obs["status"] == "error"
    assert obs["error"] == "second"
    assert obs["attempts"] == 2


@pytest.mark.asyncio
async def test_backoff_delay_between_attempts():
    """Retry waits ~200 ms (a small delay) before the second try.

    We tolerate jitter; the assertion is only that there *was* a measurable gap.
    """
    import time

    t = _fake_tool("web_search", side_effect=[RuntimeError("first"), "result"])
    started = time.perf_counter()
    obs = await _execute_with_retry(t, {"q": "x"})
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert obs["status"] == "ok"
    assert elapsed_ms >= 150  # at least ~200 ms minus jitter


@pytest.mark.asyncio
async def test_parallel_executions_via_gather():
    """Two _execute_with_retry calls in asyncio.gather complete concurrently."""
    import time

    async def slow(_input):
        await asyncio.sleep(0.1)
        return "ok"

    t1 = MagicMock(); t1.name = "t1"; t1.ainvoke = slow
    t2 = MagicMock(); t2.name = "t2"; t2.ainvoke = slow

    started = time.perf_counter()
    a, b = await asyncio.gather(
        _execute_with_retry(t1, {}),
        _execute_with_retry(t2, {}),
    )
    elapsed = time.perf_counter() - started

    assert a["status"] == "ok" and b["status"] == "ok"
    # Two 100 ms sleeps in parallel: ~100 ms total, not 200 ms.
    assert elapsed < 0.18, f"expected parallel (<180ms), got {elapsed*1000:.0f}ms"
