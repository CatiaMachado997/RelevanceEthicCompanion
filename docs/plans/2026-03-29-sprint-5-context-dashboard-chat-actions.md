# Sprint 5: 360° Context Snapshot + Dashboard Today View + Chat Follow-up Actions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `ContextSnapshotService` that computes the user's live work state from PostgreSQL, expose it as a `/api/context/snapshot` endpoint, replace the dashboard home page with an actionable "Today" view that reads from the snapshot, and add follow-up action buttons (Extract Tasks, Save as Note) to completed AI chat messages.

**Architecture:** The snapshot is a pure synchronous M1 (PostgreSQL) query — no LLM, no Weaviate, fast. It joins `tasks + projects + events + goals` into a single dict. The dashboard page calls the snapshot endpoint on load instead of making five separate API calls. Chat follow-up actions are frontend-only and reuse the existing `/api/tasks/extract` and `/api/values` endpoints — no new backend routes needed.

**Tech Stack:** FastAPI · psycopg3 (dict_row) · Supabase Auth · pytest · Next.js 15 App Router · TypeScript · Tailwind CSS v4 · lucide-react

---

## Critical Conventions

> **Read this before touching any file.**

- **`get_db_connection()`** is a context manager that auto-commits on exit. **Never call `conn.commit()` inside a `with get_db_connection()` block.**
- **All DB row access uses dict_row**: `row['column_name']`, never `row[0]`.
- **Auth helpers**: `get_current_read_user_id` for GET routes, `get_current_user_id` for write routes.
- **ESL is mandatory for all write actions.** The snapshot route is read-only — no ESL needed.
- **CSS variables** for all colours: `var(--ec-card-bg)`, `var(--ec-card-border)`, `var(--ec-card-shadow)`, `var(--ec-text)`, `var(--ec-text-subtle)`, `var(--ec-sidebar-bg)`.
- **`api` export object** lives in `frontend/lib/api.ts`. Add new API clients there and wire them into the `api` export at the bottom.
- **Table names**: calendar data is in `events` (not `calendar_events`). Columns: `id, user_id, title, description, start_time, end_time, location, source, source_id, metadata, created_at`.

---

## Scope Note

Tasks 1–4 are coupled (dashboard depends on the snapshot endpoint). Task 5 (chat follow-up actions) is fully independent and can be done in any order.

---

## File Map

### New files
- `backend/services/context_snapshot.py` — `ContextSnapshotService.compute(user_id)` — synchronous M1-only snapshot
- `backend/routes/context.py` — `GET /api/context/snapshot`
- `backend/tests/test_context_snapshot.py` — 5 tests covering service + route

### Modified files
- `backend/main.py` — import `context` router; add `app.include_router(context.router)`
- `frontend/lib/api.ts` — add `ContextSnapshot` interface; add `contextApi`; extend `api` export
- `frontend/app/dashboard/page.tsx` — replace multi-fetch loading with single snapshot call; add Today section (tasks due, projects, calendar pressure)
- `frontend/app/dashboard/chat/page.tsx` — add per-message action row (Extract Tasks + Save as Note) on completed AI messages

---

## Task 1: ContextSnapshotService

**Files:**
- Create: `backend/services/context_snapshot.py`
- Test: `backend/tests/test_context_snapshot.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_context_snapshot.py
"""Tests for ContextSnapshotService and GET /api/context/snapshot."""
import pytest
from contextlib import contextmanager
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient


# ── helpers ──────────────────────────────────────────────────────────────────

def make_db_mock(fetchall_values=None, fetchone_value=None):
    """
    Return a callable that acts as a context-manager mock for get_db_connection().

    Usage:
        with patch("services.context_snapshot.get_db_connection",
                   make_db_mock(fetchall_values=[])):
            ...
    """
    if fetchall_values is None:
        fetchall_values = []
    if fetchone_value is None:
        fetchone_value = {"cnt": 0}

    cur = MagicMock()
    cur.fetchall.return_value = fetchall_values
    cur.fetchone.return_value = fetchone_value

    cur_ctx = MagicMock()
    cur_ctx.__enter__ = MagicMock(return_value=cur)
    cur_ctx.__exit__ = MagicMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = cur_ctx
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def _db():
        yield conn

    return _db


# ── ContextSnapshotService ────────────────────────────────────────────────────

def test_compute_returns_all_required_keys():
    """compute() returns a dict with every required snapshot key."""
    with patch("services.context_snapshot.get_db_connection", make_db_mock()):
        from services.context_snapshot import ContextSnapshotService
        snapshot = ContextSnapshotService().compute("00000000-0000-0000-0000-000000000000")

    for key in ("computed_at", "tasks_due_soon", "overdue_count",
                "active_projects", "upcoming_events", "active_goals",
                "calendar_pressure"):
        assert key in snapshot, f"Missing key: {key}"


def test_calendar_pressure_light_when_no_events():
    """calendar_pressure is 'light' when there are zero upcoming events."""
    with patch("services.context_snapshot.get_db_connection", make_db_mock()):
        from services.context_snapshot import ContextSnapshotService
        snapshot = ContextSnapshotService().compute("00000000-0000-0000-0000-000000000000")

    assert snapshot["calendar_pressure"] == "light"


def test_calendar_pressure_valid_values():
    """calendar_pressure is always one of the three valid strings."""
    with patch("services.context_snapshot.get_db_connection", make_db_mock()):
        from services.context_snapshot import ContextSnapshotService
        snapshot = ContextSnapshotService().compute("00000000-0000-0000-0000-000000000000")

    assert snapshot["calendar_pressure"] in ("light", "moderate", "heavy")


def test_overdue_count_from_db():
    """overdue_count is taken from the fetchone result."""
    with patch("services.context_snapshot.get_db_connection",
               make_db_mock(fetchone_value={"cnt": 3})):
        from services.context_snapshot import ContextSnapshotService
        snapshot = ContextSnapshotService().compute("00000000-0000-0000-0000-000000000000")

    assert snapshot["overdue_count"] == 3


# ── Route ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_read_auth(monkeypatch):
    monkeypatch.setattr(
        "utils.supabase_auth.get_current_read_user_id",
        lambda: "00000000-0000-0000-0000-000000000000",
    )


def test_snapshot_route_returns_200(mock_read_auth):
    """GET /api/context/snapshot returns 200 with snapshot keys."""
    with patch("services.context_snapshot.get_db_connection", make_db_mock()):
        from main import app
        client = TestClient(app)
        response = client.get("/api/context/snapshot")

    assert response.status_code == 200
    data = response.json()
    assert "computed_at" in data
    assert "calendar_pressure" in data
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd backend
pytest tests/test_context_snapshot.py -v
```

Expected: `ModuleNotFoundError` for `services.context_snapshot` — the file doesn't exist yet.

- [ ] **Step 3: Write the implementation**

```python
# backend/services/context_snapshot.py
"""
360° User Context Snapshot

Synchronously queries M1 (PostgreSQL) to build a summary of the user's
current work state. Used by the dashboard Today view and injected into
the chat system prompt.

No LLM calls. No Weaviate. Just fast SQL.
"""
from datetime import datetime, timedelta, timezone
from typing import Any
import logging

from utils.db import get_db_connection

logger = logging.getLogger(__name__)
UTC = timezone.utc


class ContextSnapshotService:
    """Compute a point-in-time 360° context snapshot from PostgreSQL."""

    def compute(self, user_id: str) -> dict[str, Any]:
        now = datetime.now(UTC)
        in_7_days = now + timedelta(days=7)
        in_24h = now + timedelta(hours=24)

        snapshot: dict[str, Any] = {
            "computed_at": now.isoformat(),
            "tasks_due_soon": [],
            "overdue_count": 0,
            "active_projects": [],
            "upcoming_events": [],
            "active_goals": [],
            "calendar_pressure": "light",
        }

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Tasks due within the next 7 days (not done/cancelled)
                cur.execute(
                    """
                    SELECT t.id, t.title, t.status, t.due_date, t.priority,
                           p.title AS project_title
                    FROM tasks t
                    LEFT JOIN projects p ON p.id = t.project_id
                    WHERE t.user_id = %s
                      AND t.status NOT IN ('done', 'cancelled')
                      AND t.due_date IS NOT NULL
                      AND t.due_date <= %s
                    ORDER BY t.due_date ASC, t.priority DESC
                    LIMIT 10
                    """,
                    (user_id, in_7_days),
                )
                snapshot["tasks_due_soon"] = [
                    {
                        "id": str(r["id"]),
                        "title": r["title"],
                        "status": r["status"],
                        "due_date": r["due_date"].isoformat() if r["due_date"] else None,
                        "priority": r["priority"],
                        "project_title": r["project_title"],
                    }
                    for r in cur.fetchall()
                ]

                # Count overdue tasks (past due, not done/cancelled)
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM tasks
                    WHERE user_id = %s
                      AND status NOT IN ('done', 'cancelled')
                      AND due_date IS NOT NULL
                      AND due_date < %s
                    """,
                    (user_id, now),
                )
                row = cur.fetchone()
                snapshot["overdue_count"] = row["cnt"] if row else 0

                # Active projects with open/done task counts
                cur.execute(
                    """
                    SELECT p.id, p.title,
                           COUNT(t.id) FILTER (
                               WHERE t.status NOT IN ('done', 'cancelled')
                           ) AS open_tasks,
                           COUNT(t.id) FILTER (
                               WHERE t.status = 'done'
                           ) AS done_tasks
                    FROM projects p
                    LEFT JOIN tasks t ON t.project_id = p.id
                    WHERE p.user_id = %s AND p.status = 'active'
                    GROUP BY p.id, p.title
                    ORDER BY p.updated_at DESC
                    LIMIT 5
                    """,
                    (user_id,),
                )
                snapshot["active_projects"] = [
                    {
                        "id": str(r["id"]),
                        "title": r["title"],
                        "open_tasks": r["open_tasks"],
                        "done_tasks": r["done_tasks"],
                    }
                    for r in cur.fetchall()
                ]

                # Upcoming events in the next 24h (from the 'events' table)
                cur.execute(
                    """
                    SELECT title, start_time, location
                    FROM events
                    WHERE user_id = %s
                      AND start_time >= %s
                      AND start_time <= %s
                    ORDER BY start_time ASC
                    LIMIT 5
                    """,
                    (user_id, now, in_24h),
                )
                events = cur.fetchall()
                snapshot["upcoming_events"] = [
                    {
                        "title": r["title"],
                        "start_time": r["start_time"].isoformat() if r["start_time"] else None,
                        "location": r["location"],
                    }
                    for r in events
                ]
                event_count = len(events)
                snapshot["calendar_pressure"] = (
                    "heavy" if event_count >= 4
                    else "moderate" if event_count >= 2
                    else "light"
                )

                # Top active goals
                cur.execute(
                    """
                    SELECT id, title, priority, target_date
                    FROM goals
                    WHERE user_id = %s AND status = 'active'
                    ORDER BY priority ASC
                    LIMIT 5
                    """,
                    (user_id,),
                )
                snapshot["active_goals"] = [
                    {
                        "id": str(r["id"]),
                        "title": r["title"],
                        "priority": r["priority"],
                        "target_date": (
                            r["target_date"].isoformat() if r["target_date"] else None
                        ),
                    }
                    for r in cur.fetchall()
                ]

        return snapshot
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
cd backend
pytest tests/test_context_snapshot.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/services/context_snapshot.py backend/tests/test_context_snapshot.py
git commit -m "feat: add ContextSnapshotService — 360° M1 context from tasks/projects/events/goals"
```

---

## Task 2: Context Snapshot API Route

**Files:**
- Create: `backend/routes/context.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create the route file**

```python
# backend/routes/context.py
"""Context snapshot API route."""
from fastapi import APIRouter, Depends
from typing import Any, Dict

from utils.supabase_auth import get_current_read_user_id
from services.context_snapshot import ContextSnapshotService

router = APIRouter(prefix="/api/context", tags=["Context"])


@router.get("/snapshot", response_model=Dict[str, Any])
async def get_snapshot(user_id: str = Depends(get_current_read_user_id)):
    """Return the user's current 360° context snapshot."""
    service = ContextSnapshotService()
    return service.compute(str(user_id))
```

- [ ] **Step 2: Register the router in main.py**

In `backend/main.py`, line 169, extend the grouped import:

```python
# Before:
from routes import auth, values, chat, goals, transparency, relevance, data_sources, profile, notifications, feedback, search, documents, projects, tasks

# After:
from routes import auth, values, chat, goals, transparency, relevance, data_sources, profile, notifications, feedback, search, documents, projects, tasks, context
```

After `app.include_router(tasks.router)` (around line 191), add:

```python
app.include_router(context.router)
```

- [ ] **Step 3: Verify the route is reachable**

```bash
cd backend
python -c "from routes.context import router; print('OK', router.prefix)"
```

Expected output: `OK /api/context`

- [ ] **Step 4: Run full test suite — confirm nothing broken**

```bash
cd backend
pytest --tb=short -q
```

Expected: all previously passing tests still pass, new snapshot tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/context.py backend/main.py
git commit -m "feat: add GET /api/context/snapshot route"
```

---

## Task 3: Frontend API Client

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add the `ContextSnapshot` interface and `contextApi`**

Find the block of interface definitions near the top of `frontend/lib/api.ts` (around where `Project` and `Task` are defined) and add after them:

```typescript
export interface ContextSnapshotTask {
  id: string
  title: string
  status: string
  due_date: string | null
  priority: number
  project_title: string | null
}

export interface ContextSnapshotProject {
  id: string
  title: string
  open_tasks: number
  done_tasks: number
}

export interface ContextSnapshotEvent {
  title: string
  start_time: string | null
  location: string | null
}

export interface ContextSnapshotGoal {
  id: string
  title: string
  priority: number
  target_date: string | null
}

export interface ContextSnapshot {
  computed_at: string
  tasks_due_soon: ContextSnapshotTask[]
  overdue_count: number
  active_projects: ContextSnapshotProject[]
  upcoming_events: ContextSnapshotEvent[]
  active_goals: ContextSnapshotGoal[]
  calendar_pressure: 'light' | 'moderate' | 'heavy'
}
```

Then add the API client (before the `export const api = {` block at the bottom):

```typescript
export const contextApi = {
  snapshot: (): Promise<ContextSnapshot> =>
    apiRequest<ContextSnapshot>('/api/context/snapshot'),
}
```

In the `export const api = { ... }` object at the bottom, add:

```typescript
  context: contextApi,
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors from `api.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add contextApi and ContextSnapshot types to frontend API client"
```

---

## Task 4: Dashboard Today View

**Files:**
- Modify: `frontend/app/dashboard/page.tsx`

The current dashboard makes 5 separate API calls (goals, values, transparency report, ESL logs, events) and shows stats + a daily insight. This task adds a **Today** section at the top of the page that reads from the snapshot. The existing ESL activity + daily insight sections are kept.

- [ ] **Step 1: Replace the top of the file — update imports and state**

Open `frontend/app/dashboard/page.tsx`. Replace the existing import block and state declarations with the version below. The key change is adding `contextApi` and `ContextSnapshot` to the import, and a `snapshot` state variable.

```typescript
'use client'

import { useEffect, useState } from 'react'
import { transparencyApi, insightApi, contextApi, type ContextSnapshot } from '@/lib/api'
import Link from 'next/link'
import {
  MessageSquare, Shield, ArrowRight, Target, Calendar,
  Clock, AlertTriangle, CheckSquare, FolderOpen, Zap,
} from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Card } from '@/components/ui/card'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

interface ESLLog {
  id?: string
  decision?: { status: 'APPROVED' | 'VETOED' | 'MODIFIED'; reason: string }
  timestamp?: string
}

const CARD_STYLE = {
  background: 'var(--ec-card-bg)',
  border: '1px solid var(--ec-card-border)',
  borderRadius: '16px',
  boxShadow: 'var(--ec-card-shadow)',
}

const ESL_COLORS = {
  APPROVED: { bg: 'rgba(74,124,89,0.10)',  text: '#4A7C59', border: 'rgba(74,124,89,0.20)' },
  VETOED:   { bg: 'rgba(176,74,58,0.10)',  text: '#B04A3A', border: 'rgba(176,74,58,0.20)' },
  MODIFIED: { bg: 'rgba(155,122,61,0.10)', text: '#9B7A3D', border: 'rgba(155,122,61,0.20)' },
}

const PRESSURE_LABEL: Record<string, string> = {
  light: 'Light day',
  moderate: 'Moderate load',
  heavy: 'Heavy schedule',
}
const PRESSURE_COLOR: Record<string, string> = {
  light: '#4A7C59',
  moderate: '#9B7A3D',
  heavy: '#B04A3A',
}
```

- [ ] **Step 2: Update `DashboardPage` — replace the `useEffect` and add Today state**

Replace the component function signature and `useEffect` with:

```typescript
export default function DashboardPage() {
  const [snapshot, setSnapshot] = useState<ContextSnapshot | null>(null)
  const [eslActivity, setEslActivity] = useState<ESLLog[]>([])
  const [approvalRate, setApprovalRate] = useState<number | null>(null)
  const [eslCount, setEslCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [dailyInsight, setDailyInsight] = useState<string | null>(null)
  const [insightLoading, setInsightLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [snap, report, logs] = await Promise.allSettled([
          contextApi.snapshot(),
          transparencyApi.report(),
          transparencyApi.logs(),
        ])
        if (snap.status === 'fulfilled') setSnapshot(snap.value)
        if (report.status === 'fulfilled') {
          setEslCount(report.value?.total_decisions ?? 0)
          const rate = report.value?.approval_rate ?? 0
          setApprovalRate(rate > 1 ? rate : rate * 100)
        }
        if (logs.status === 'fulfilled')
          setEslActivity((logs.value?.logs ?? []).slice(0, 5) as unknown as ESLLog[])
      } finally {
        setLoading(false)
      }

      try {
        const insightData = await insightApi.daily()
        setDailyInsight(insightData?.insight ?? null)
      } catch {}
      setInsightLoading(false)
    }
    load()
  }, [])
```

- [ ] **Step 3: Add the Today section to the JSX**

Inside the component's `return (...)`, add the Today section **before** the existing ESL/insight sections:

```tsx
{/* ── Today section ─────────────────────────────────────────── */}
<div className="mb-8">
  <div className="flex items-center justify-between mb-4">
    <h2 className="text-base font-semibold" style={{ color: 'var(--ec-text)' }}>
      Today
    </h2>
    {snapshot && (
      <span
        className="text-xs px-2 py-0.5 rounded-full font-medium"
        style={{
          background: `${PRESSURE_COLOR[snapshot.calendar_pressure]}18`,
          color: PRESSURE_COLOR[snapshot.calendar_pressure],
          border: `1px solid ${PRESSURE_COLOR[snapshot.calendar_pressure]}30`,
        }}
      >
        {PRESSURE_LABEL[snapshot.calendar_pressure]}
      </span>
    )}
  </div>

  {loading ? (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {[0, 1].map(i => <Skeleton key={i} className="h-32 rounded-2xl" />)}
    </div>
  ) : (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

      {/* Tasks due soon */}
      <div style={CARD_STYLE} className="p-5">
        <div className="flex items-center gap-2 mb-3">
          <CheckSquare size={14} style={{ color: 'var(--ec-text-subtle)' }} />
          <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
            Due soon
          </span>
          {snapshot && snapshot.overdue_count > 0 && (
            <span
              className="ml-auto text-xs px-1.5 py-0.5 rounded-full font-medium flex items-center gap-1"
              style={{ background: 'rgba(176,74,58,0.10)', color: '#B04A3A' }}
            >
              <AlertTriangle size={10} />
              {snapshot.overdue_count} overdue
            </span>
          )}
        </div>
        {!snapshot || snapshot.tasks_due_soon.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--ec-text-subtle)' }}>
            No tasks due in the next 7 days.{' '}
            <Link href="/dashboard/tasks" className="underline">Add one</Link>
          </p>
        ) : (
          <ul className="space-y-2">
            {snapshot.tasks_due_soon.slice(0, 4).map(t => (
              <li key={t.id} className="flex items-start gap-2">
                <span
                  className="mt-0.5 w-1.5 h-1.5 rounded-full shrink-0"
                  style={{
                    background: t.status === 'in_progress' ? '#4A7C59' : 'var(--ec-text-subtle)',
                    marginTop: '6px',
                  }}
                />
                <div className="min-w-0">
                  <p className="text-sm truncate" style={{ color: 'var(--ec-text)' }}>{t.title}</p>
                  <p className="text-[11px]" style={{ color: 'var(--ec-text-subtle)' }}>
                    {t.project_title ? `${t.project_title} · ` : ''}
                    {t.due_date
                      ? new Date(t.due_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                      : 'No due date'}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
        <Link
          href="/dashboard/tasks"
          className="mt-3 flex items-center gap-1 text-xs hover:opacity-70 transition-opacity"
          style={{ color: '#4A7C59' }}
        >
          All tasks <ArrowRight size={11} />
        </Link>
      </div>

      {/* Active projects */}
      <div style={CARD_STYLE} className="p-5">
        <div className="flex items-center gap-2 mb-3">
          <FolderOpen size={14} style={{ color: 'var(--ec-text-subtle)' }} />
          <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
            Active projects
          </span>
        </div>
        {!snapshot || snapshot.active_projects.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--ec-text-subtle)' }}>
            No active projects.{' '}
            <Link href="/dashboard/projects" className="underline">Create one</Link>
          </p>
        ) : (
          <ul className="space-y-2.5">
            {snapshot.active_projects.slice(0, 4).map(p => {
              const total = p.open_tasks + p.done_tasks
              const pct = total > 0 ? Math.round((p.done_tasks / total) * 100) : 0
              return (
                <li key={p.id}>
                  <div className="flex items-center justify-between mb-0.5">
                    <p className="text-sm truncate flex-1 mr-2" style={{ color: 'var(--ec-text)' }}>{p.title}</p>
                    <span className="text-[11px] shrink-0" style={{ color: 'var(--ec-text-subtle)' }}>
                      {p.open_tasks} open
                    </span>
                  </div>
                  <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--ec-card-border)' }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${pct}%`, background: '#4A7C59' }}
                    />
                  </div>
                </li>
              )
            })}
          </ul>
        )}
        <Link
          href="/dashboard/projects"
          className="mt-3 flex items-center gap-1 text-xs hover:opacity-70 transition-opacity"
          style={{ color: '#4A7C59' }}
        >
          All projects <ArrowRight size={11} />
        </Link>
      </div>

      {/* Upcoming events */}
      {snapshot && snapshot.upcoming_events.length > 0 && (
        <div style={CARD_STYLE} className="p-5 md:col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <Calendar size={14} style={{ color: 'var(--ec-text-subtle)' }} />
            <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
              Next 24 hours
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {snapshot.upcoming_events.map((ev, i) => (
              <div
                key={i}
                className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-sm"
                style={{ background: 'var(--ec-surface-2, rgba(0,0,0,0.04))', color: 'var(--ec-text)' }}
              >
                <Clock size={12} style={{ color: 'var(--ec-text-subtle)' }} />
                <span>{ev.title}</span>
                {ev.start_time && (
                  <span style={{ color: 'var(--ec-text-subtle)' }}>
                    {new Date(ev.start_time).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  )}
</div>
```

- [ ] **Step 4: Verify the page compiles**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no type errors.

- [ ] **Step 5: Start dev server and visually verify**

```bash
cd frontend
npm run dev
```

Open http://localhost:3000/dashboard. Check:
- "Today" section loads (or shows skeletons while loading)
- Tasks due soon list renders (or shows "No tasks due" empty state)
- Active projects with progress bars render
- Calendar events row renders if events exist
- Calendar pressure badge shows in header

- [ ] **Step 6: Commit**

```bash
git add frontend/app/dashboard/page.tsx
git commit -m "feat: replace dashboard home with Today view — snapshot-driven tasks, projects, events"
```

---

## Task 5: Chat Follow-up Action Buttons

**Files:**
- Modify: `frontend/app/dashboard/chat/page.tsx`

Add two action buttons below each completed (non-streaming) AI message:
- **Extract Tasks** → sends message content to `/api/tasks/extract`, shows returned suggestions in an inline panel, user clicks "Add" per task → calls `tasksApi.create()`
- **Save as Note** → calls `api.values.create()` with `type='preference'` and `metadata.subtype='note'`, shows a brief inline confirmation

Both use existing API endpoints — no new backend work needed.

- [ ] **Step 1: Add imports**

At the top of `frontend/app/dashboard/chat/page.tsx`, the existing import from `@/lib/api` already includes the api object. Make sure `tasksApi` and `valuesApi` (or `api.tasks` and `api.values`) are accessible. They are already in the `api` export. Also add `BookmarkPlus, ListTodo` to the lucide-react import:

Find the lucide import line and add `BookmarkPlus, ListTodo, CheckCircle`:

```typescript
import {
  Send, ChevronDown, ChevronUp, Copy, Square,
  ThumbsUp, ThumbsDown, RotateCcw, Plus, Cpu,
  Paperclip, Globe, Calendar, Target, StickyNote,
  BarChart2, ShieldCheck, Sparkles,
  BookmarkPlus, ListTodo, CheckCircle,   // ← add these three
} from 'lucide-react'
```

- [ ] **Step 2: Add per-message follow-up state**

Inside `ChatPage`, add state for the extract panel and save confirmation:

```typescript
const [extractingFor, setExtractingFor] = useState<string | null>(null)      // message index
const [extractedSuggestions, setExtractedSuggestions] = useState<import('@/lib/api').ExtractedTask[]>([])
const [extractLoading, setExtractLoading] = useState(false)
const [savedNoteFor, setSavedNoteFor] = useState<string | null>(null)         // message index
```

- [ ] **Step 3: Add handler functions**

Inside `ChatPage`, after the existing handlers, add:

```typescript
const handleExtractTasks = async (content: string, msgKey: string) => {
  setExtractingFor(msgKey)
  setExtractedSuggestions([])
  setExtractLoading(true)
  try {
    const result = await api.tasks.extract(content)
    setExtractedSuggestions(result.suggestions ?? [])
  } catch {
    setExtractedSuggestions([])
  } finally {
    setExtractLoading(false)
  }
}

const handleConfirmTask = async (suggestion: import('@/lib/api').ExtractedTask) => {
  await api.tasks.create({
    title: suggestion.title,
    description: suggestion.description ?? undefined,
    priority: suggestion.priority ?? 5,
    source_origin: 'ai_chat',
    ai_confidence: suggestion.confidence ?? undefined,
  })
  setExtractedSuggestions(prev => prev.filter(s => s.title !== suggestion.title))
}

const handleSaveNote = async (content: string, msgKey: string) => {
  await api.values.create({
    type: 'preference',
    value: content.slice(0, 1000),
    priority: 5,
    metadata: { subtype: 'note', source: 'chat_response' },
  })
  setSavedNoteFor(msgKey)
  setTimeout(() => setSavedNoteFor(null), 3000)
}
```

- [ ] **Step 4: Render the action row and extract panel below AI messages**

Find where assistant messages are rendered (look for `msg.role === 'assistant'` or the `CompanionAvatar` component). Below the `<div className="chat-prose ...">` that renders `ReactMarkdown`, and **outside** the `{msg.streaming && ...}` condition (only show for completed messages), add:

```tsx
{/* Follow-up actions — only on completed, non-streaming messages */}
{!msg.streaming && msg.content && (
  <div className="mt-2">
    {/* Action buttons */}
    <div className="flex items-center gap-1">
      <button
        onClick={() => handleExtractTasks(msg.content, msg.id ?? String(i))}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-colors hover:opacity-80"
        style={{
          background: 'var(--ec-surface-2, rgba(0,0,0,0.04))',
          color: 'var(--ec-text-subtle)',
          border: '1px solid var(--ec-card-border)',
        }}
        title="Extract tasks from this response"
      >
        <ListTodo size={11} />
        Extract tasks
      </button>
      <button
        onClick={() => handleSaveNote(msg.content, msg.id ?? String(i))}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-colors hover:opacity-80"
        style={{
          background: savedNoteFor === (msg.id ?? String(i))
            ? 'rgba(74,124,89,0.10)'
            : 'var(--ec-surface-2, rgba(0,0,0,0.04))',
          color: savedNoteFor === (msg.id ?? String(i)) ? '#4A7C59' : 'var(--ec-text-subtle)',
          border: '1px solid var(--ec-card-border)',
        }}
        title="Save this response as a note"
      >
        {savedNoteFor === (msg.id ?? String(i))
          ? <><CheckCircle size={11} /> Saved</>
          : <><BookmarkPlus size={11} /> Save as note</>
        }
      </button>
    </div>

    {/* Extract panel */}
    {extractingFor === (msg.id ?? String(i)) && (
      <div
        className="mt-3 rounded-xl p-4"
        style={{
          background: 'var(--ec-card-bg)',
          border: '1px solid var(--ec-card-border)',
        }}
      >
        <p className="text-xs font-medium mb-2" style={{ color: 'var(--ec-text)' }}>
          Extracted tasks
        </p>
        {extractLoading ? (
          <p className="text-xs" style={{ color: 'var(--ec-text-subtle)' }}>Analysing…</p>
        ) : extractedSuggestions.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--ec-text-subtle)' }}>No tasks found.</p>
        ) : (
          <ul className="space-y-2">
            {extractedSuggestions.map((s, si) => (
              <li key={si} className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: 'var(--ec-text)' }}>
                    {s.title}
                  </p>
                  {s.description && (
                    <p className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--ec-text-subtle)' }}>
                      {s.description}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleConfirmTask(s)}
                  className="shrink-0 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors hover:opacity-80"
                  style={{ background: '#4A7C59', color: '#fff' }}
                >
                  Add
                </button>
              </li>
            ))}
          </ul>
        )}
        <button
          onClick={() => { setExtractingFor(null); setExtractedSuggestions([]) }}
          className="mt-2 text-xs hover:opacity-70"
          style={{ color: 'var(--ec-text-subtle)' }}
        >
          Dismiss
        </button>
      </div>
    )}
  </div>
)}
```

**Note on `msg.id` vs `String(i)`**: The message objects in the chat array may or may not have a stable `id` field. Check the message type definition in the file. If messages have a `conversationId` or similar, use that as the key. If not, `String(i)` (the index) is fine as a fallback — messages don't reorder after rendering.

- [ ] **Step 5: TypeScript check**

```bash
cd frontend
npx tsc --noEmit
```

Fix any type errors (e.g., `msg.id` not existing on the message type — replace with the correct field or index).

- [ ] **Step 6: Smoke test**

Start the dev server (`npm run dev`), open a chat, send a message, wait for the AI response to complete. Verify:
- "Extract tasks" and "Save as note" buttons appear below the completed AI message
- Clicking "Save as note" changes button to "✓ Saved" for 3 seconds
- Clicking "Extract tasks" shows the loading state, then task suggestions
- Clicking "Add" on a suggestion adds it to Tasks (verify via `/dashboard/tasks`)
- Clicking "Dismiss" hides the extract panel

- [ ] **Step 7: Commit**

```bash
git add frontend/app/dashboard/chat/page.tsx
git commit -m "feat: add Extract Tasks and Save as Note follow-up actions to chat messages"
```

---

## Verification Checklist

Run after all tasks are complete:

```bash
# Backend
cd backend
pytest tests/test_context_snapshot.py -v   # 5 tests pass
pytest --tb=short -q                        # all tests pass

# Frontend
cd frontend
npx tsc --noEmit                            # no type errors
```

Manual end-to-end:
1. Open `/dashboard` → Today section loads with tasks, projects, events
2. Navigate to `/dashboard/chat` → send message → action buttons appear on AI response
3. Click "Extract tasks" → suggestions appear → click "Add" → task appears in `/dashboard/tasks`
4. Click "Save as note" → confirmation shown → note appears in `/dashboard/values`
5. Return to `/dashboard` → overdue count badge shows if overdue tasks exist

---

## Critical Files Reference

| File | Change |
|------|--------|
| `backend/services/context_snapshot.py` | New — ContextSnapshotService |
| `backend/routes/context.py` | New — GET /api/context/snapshot |
| `backend/main.py` | +1 import, +1 include_router |
| `backend/tests/test_context_snapshot.py` | New — 5 tests |
| `frontend/lib/api.ts` | +ContextSnapshot types, +contextApi, +api.context |
| `frontend/app/dashboard/page.tsx` | Replace multi-fetch with snapshot; add Today section |
| `frontend/app/dashboard/chat/page.tsx` | Add Extract Tasks + Save as Note action row |
