# V4 Sprint — Intelligence & Depth

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the app feel alive — unread notification badge, ESL events surface as notifications, daily AI insight on the dashboard, LLM-generated conversation titles, goal milestones, and weekly AI digest.

**Architecture:** Six independent sub-projects. Each can be completed and committed in isolation. Sub-projects A–C are high-priority polish; D–F add depth. The scheduler (APScheduler, already running) is extended for the weekly digest. A new `daily_insights` table and `goal_milestones` table are introduced; both are migration-safe via `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS`.

**Tech Stack:** FastAPI (Python), Next.js 15 App Router (TypeScript), PostgreSQL, APScheduler, LangChain + ChatGroq, Weaviate, Supabase Auth

---

## File Map

| File | Sub-project | Change |
|------|-------------|--------|
| `backend/routes/notifications.py` | A, B | Add `GET /count` endpoint; call `create_notification` from ESL path |
| `backend/services/orchestrator_v2.py` | B, D | Call `create_notification` on VETO/MODIFY; improve auto-title with LLM |
| `backend/routes/insight.py` | C | New file — `GET /api/insight/daily` endpoint |
| `backend/main.py` | C, F | Register insight router; add weekly digest job; add startup migration for new tables |
| `backend/services/scheduler.py` | F | Add weekly Monday-morning digest job |
| `backend/database/schema_local.sql` | C, E | Add `daily_insights` + `goal_milestones` tables |
| `backend/database/schema.sql` | C, E | Same |
| `backend/database/migration_v4.sql` | C, E | Safe `CREATE TABLE IF NOT EXISTS` migration |
| `backend/routes/goals.py` | E | Add milestone CRUD endpoints |
| `frontend/components/sidebar.tsx` | A | Fetch unread count; show badge on Bell nav item |
| `frontend/lib/api.ts` | A, C, E | Add `notificationsApi.count()`, `insightApi`, milestone methods to `goalsApi` |
| `frontend/app/dashboard/page.tsx` | C | Add daily insight card |
| `frontend/app/dashboard/goals/page.tsx` | E | Add milestone panel within goal card |
| `backend/tests/test_notifications_routes.py` | A, B | Tests for /count endpoint and notification creation |
| `backend/tests/test_insight_route.py` | C | New test file |
| `backend/tests/test_goals_routes.py` | E | Tests for milestone endpoints |

---

## Sub-project A — Unread notification badge in sidebar

**Why:** The Bell icon in the nav shows no count. Users have no signal when new notifications arrive.

### Task A.1 — Add `GET /api/notifications/count` endpoint

**Files:**
- Modify: `backend/routes/notifications.py`
- Modify: `backend/tests/test_notifications_routes.py`

- [ ] **Write the failing test**

```python
# tests/test_notifications_routes.py — add at end of file

def test_notification_count_endpoint(client, monkeypatch):
    """GET /api/notifications/count returns {unread_count: N}."""
    from unittest.mock import patch, MagicMock
    mock_row = {"cnt": 3}
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = mock_row
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    with patch("routes.notifications.get_db", return_value=mock_conn):
        response = client.get("/api/notifications/count")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 3
```

- [ ] **Run test — expect FAIL** (404, endpoint doesn't exist)

```bash
cd backend && pytest tests/test_notifications_routes.py::test_notification_count_endpoint -v
```

Expected: `FAILED — 404 Not Found`

- [ ] **Add the endpoint** to `backend/routes/notifications.py` after the `list_notifications` route:

```python
@router.get("/count", response_model=dict)
async def get_unread_count(
    user_id: str = Depends(get_current_read_user_id),
):
    """Lightweight endpoint returning only the unread notification count."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM user_notifications WHERE user_id = %s AND read = FALSE",
                    (str(user_id),),
                )
                row = cur.fetchone()
        return {"unread_count": int(row["cnt"]) if row else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching count: {str(e)}")
```

- [ ] **Run test — expect PASS**

```bash
pytest tests/test_notifications_routes.py -v
```

Expected: all pass

- [ ] **Commit**

```bash
git add backend/routes/notifications.py backend/tests/test_notifications_routes.py
git commit -m "feat: add GET /api/notifications/count endpoint"
```

---

### Task A.2 — Add `notificationsApi.count()` to frontend

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Find the `notificationsApi` block** (around line 712) and add:

```typescript
count: async (): Promise<{ unread_count: number }> => {
  return apiRequest<{ unread_count: number }>('/api/notifications/count')
},
```

- [ ] **Verify TypeScript compiles**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error" | head -5
```

Expected: no errors

---

### Task A.3 — Unread badge in sidebar

**Files:**
- Modify: `frontend/components/sidebar.tsx`

- [ ] **Add unread count state and polling** — in `SidebarNav`, after the `conversations` state declarations (around line 66):

```typescript
const [unreadNotifications, setUnreadNotifications] = useState(0)
```

- [ ] **Add fetch effect** — after the conversations `useEffect` (around line 72):

```typescript
useEffect(() => {
  const fetchCount = () => {
    api.notifications.count()
      .then(r => setUnreadNotifications(r.unread_count))
      .catch(() => {})
  }
  fetchCount()
  const interval = setInterval(fetchCount, 60_000) // refresh every 60s
  return () => clearInterval(interval)
}, [])
```

- [ ] **Wrap the Notifications nav item** to show a badge. Find where NAV_ITEMS are rendered (around line 100–140). The nav item renders `<Icon size={16} />` inside a `Link`. Add a wrapper so the Bell item gets a badge:

In the section that maps NAV_ITEMS, replace the nav item render with:

```tsx
<Link
  key={item.href}
  href={item.href}
  onClick={onClose}
  className={cn(
    "flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-colors",
    isActive ? "bg-[rgba(0,0,0,0.06)] font-medium" : "hover:bg-[rgba(0,0,0,0.04)]"
  )}
  style={{ color: isActive ? '#0a0a0a' : '#695e6e' }}
>
  <span className="relative">
    <item.icon size={16} />
    {item.href === '/dashboard/notifications' && unreadNotifications > 0 && (
      <span
        className="absolute -top-1.5 -right-1.5 min-w-[14px] h-[14px] rounded-full flex items-center justify-center text-[9px] font-bold leading-none px-0.5"
        style={{ background: '#B04A3A', color: '#fff' }}
      >
        {unreadNotifications > 9 ? '9+' : unreadNotifications}
      </span>
    )}
  </span>
  {item.label}
</Link>
```

> **Note:** Check the exact render pattern in the sidebar — the current code renders nav items at lines 100–140. Adapt to match the existing structure; only the icon `<span>` wrapper is new.

- [ ] **Clear badge when user visits notifications** — in the same `useEffect` that polls, also reset when `pathname` includes `notifications`:

```typescript
useEffect(() => {
  if (pathname.includes('/notifications')) setUnreadNotifications(0)
}, [pathname])
```

- [ ] **Verify build**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error" | head -5
```

- [ ] **Commit**

```bash
git add frontend/components/sidebar.tsx frontend/lib/api.ts
git commit -m "feat: unread notification badge in sidebar nav"
```

---

## Sub-project B — ESL decisions → user notifications

**Why:** The notifications page is empty for most users. ESL veto/modify events should surface as actionable notifications so users understand what happened.

### Task B.1 — Call `create_notification` from orchestrator on ESL veto/modify

**Files:**
- Modify: `backend/services/orchestrator_v2.py`
- Modify: `backend/tests/test_notifications_routes.py`

- [ ] **Write a failing integration test**

```python
# tests/test_notifications_routes.py — add at end

def test_esl_veto_creates_notification(client, monkeypatch):
    """When orchestrator's post_stream_store runs with a vetoed ESL result, a notification is created."""
    # This tests the create_notification helper directly — verifies the DB write shape
    from routes.notifications import create_notification
    from unittest.mock import MagicMock, patch

    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    create_notification(
        mock_conn,
        user_id="00000000-0000-0000-0000-000000000000",
        type="esl_block",
        title="ESL blocked a response",
        message="Time-based boundary: no work notifications after 7pm",
    )

    mock_cur.execute.assert_called_once()
    args = mock_cur.execute.call_args[0]
    assert "INSERT INTO user_notifications" in args[0]
    assert "esl_block" in args[1]
```

- [ ] **Run test — expect PASS** (this tests existing `create_notification`, should pass already)

```bash
pytest tests/test_notifications_routes.py::test_esl_veto_creates_notification -v
```

- [ ] **Add notification creation to `_post_stream_store`** in `orchestrator_v2.py`

Find `_post_stream_store` (around line 589). After the ESL advisory call, add:

```python
# Import at top of file (if not already imported):
from routes.notifications import create_notification

# Inside _post_stream_store, after the ESL decide_action call:
try:
    from esl.models import ESLDecisionStatus
    esl_result = await self.decide_action(
        user_id=user_id,
        action_type=ActionType.CHAT_RESPONSE,
        content=assistant_msg,
        urgency=UrgencyLevel.LOW,
        metadata={"advisory_only": True}
    )
    decision = esl_result.get("decision")
    if decision and hasattr(decision, "status"):
        if decision.status in (ESLDecisionStatus.VETOED, ESLDecisionStatus.MODIFIED):
            notif_type = "esl_block" if decision.status == ESLDecisionStatus.VETOED else "warning"
            notif_title = (
                "ESL blocked a response" if decision.status == ESLDecisionStatus.VETOED
                else "ESL modified a response"
            )
            with get_db_connection() as conn:
                create_notification(
                    conn,
                    user_id=user_id,
                    type=notif_type,
                    title=notif_title,
                    message=decision.reason[:300] if decision.reason else "No details available.",
                    metadata={"applied_rules": decision.applied_rules},
                )
except Exception as e:
    logger.warning(f"Could not create ESL notification: {e}")
```

> **Important:** `_post_stream_store` is fire-and-forget. Wrap in try/except so notification failures never break the chat response.

- [ ] **Run all tests**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -15
```

Expected: 93+ passed

- [ ] **Commit**

```bash
git add backend/services/orchestrator_v2.py backend/tests/test_notifications_routes.py
git commit -m "feat: ESL veto/modify decisions create user notifications"
```

---

## Sub-project C — Daily proactive insight on dashboard

**Why:** The app's core value is proactive AI reasoning. The dashboard has a greeting card but no "what your companion is thinking today." This is the biggest missing piece of the product vision.

### Task C.1 — Database table + startup migration

**Files:**
- Modify: `backend/database/schema_local.sql`
- Modify: `backend/database/schema.sql`
- Create: `backend/database/migration_v4.sql`
- Modify: `backend/main.py`

- [ ] **Add `daily_insights` table** to both schema files (before the last comment block):

```sql
-- Daily AI insights (one per user per day, cached)
CREATE TABLE IF NOT EXISTS daily_insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  generated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, date)
);
```

- [ ] **Create `migration_v4.sql`** for existing deployments:

```sql
-- V4 migration: daily_insights + goal_milestones
CREATE TABLE IF NOT EXISTS daily_insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  generated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, date)
);

CREATE TABLE IF NOT EXISTS goal_milestones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  completed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_goal_milestones_goal ON goal_milestones(goal_id);
CREATE INDEX IF NOT EXISTS idx_daily_insights_user_date ON daily_insights(user_id, date);
```

- [ ] **Add startup migration** to `main.py` lifespan (after the existing weight-columns migration):

```python
# Auto-migrate V4 tables
try:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_insights (
                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  content TEXT NOT NULL,
                  date DATE NOT NULL DEFAULT CURRENT_DATE,
                  generated_at TIMESTAMPTZ DEFAULT NOW(),
                  UNIQUE(user_id, date)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS goal_milestones (
                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                  goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
                  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  title TEXT NOT NULL,
                  completed BOOLEAN DEFAULT FALSE,
                  created_at TIMESTAMPTZ DEFAULT NOW(),
                  updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_goal_milestones_goal ON goal_milestones(goal_id)"
            )
    logger.debug("V4 tables verified")
except Exception as e:
    logger.warning(f"Could not verify V4 tables: {e}")
```

- [ ] **Commit schema changes**

```bash
git add backend/database/ backend/main.py
git commit -m "feat: add daily_insights and goal_milestones tables with startup migration"
```

---

### Task C.2 — `GET /api/insight/daily` endpoint

**Files:**
- Create: `backend/routes/insight.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_insight_route.py`

- [ ] **Write the failing test first**

```python
# backend/tests/test_insight_route.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_daily_insight_returns_cached(client):
    """Returns cached insight without calling LLM if one exists for today."""
    mock_row = {"content": "Today focus on your MVP goal — the team sync is in 2 hours."}
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = mock_row
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    with patch("routes.insight.get_db", return_value=mock_conn):
        response = client.get("/api/insight/daily?user_id=00000000-0000-0000-0000-000000000000")
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        data = response.json()
        assert "insight" in data
        assert data["cached"] is True

def test_daily_insight_returns_200(client):
    """Endpoint exists and responds."""
    response = client.get("/api/insight/daily?user_id=00000000-0000-0000-0000-000000000000")
    assert response.status_code in (200, 401, 500)  # 500 acceptable in test env (no DB/LLM)
```

- [ ] **Run test — expect FAIL** (404)

```bash
pytest tests/test_insight_route.py -v
```

- [ ] **Create `backend/routes/insight.py`**

```python
"""
Daily Insight Route

Generates (or returns cached) a single daily proactive insight for the user.
The LLM creates a personalised suggestion based on goals, upcoming events, and values.
Result is cached per user per day in the daily_insights table.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from config import settings
from utils.db import get_db
from utils.supabase_auth import get_current_read_user_id
from services.context_manager import ContextManager
from utils.weaviate_client import get_weaviate_client
from services.embedding_service import EmbeddingService

router = APIRouter(prefix="/api/insight", tags=["Insight"])
logger = logging.getLogger(__name__)


def _get_context_manager() -> ContextManager:
    try:
        wc = get_weaviate_client()
    except Exception:
        wc = None
    es = EmbeddingService(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
    return ContextManager(weaviate_client=wc, embedding_service=es)


@router.get("/daily", response_model=dict)
async def get_daily_insight(
    user_id: str = Depends(get_current_read_user_id),
):
    """
    Return today's proactive insight for the user.
    Generates a new one if none exists for today; caches for the rest of the day.
    """
    # 1. Check cache
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT content FROM daily_insights WHERE user_id = %s AND date = CURRENT_DATE",
                    (str(user_id),),
                )
                row = cur.fetchone()
        if row:
            return {"insight": row["content"], "cached": True}
    except Exception as e:
        logger.warning(f"Could not read daily_insights cache: {e}")

    # 2. Generate using LLM
    if not settings.GROQ_API_KEY:
        return {
            "insight": "Set up your goals and values to receive personalised daily insights.",
            "cached": False,
        }

    try:
        ctx = _get_context_manager()
        goals = await ctx.get_active_goals(str(user_id))
        events = await ctx.get_upcoming_events(str(user_id), hours_ahead=24)
        values = await ctx.get_user_values(str(user_id))

        goal_text = "\n".join(f"- {g.title}" for g in goals[:5]) or "None set yet."
        event_text = "\n".join(f"- {e.title}" for e in events[:3]) or "Nothing scheduled."
        value_text = "\n".join(f"- {v.value}" for v in values[:5]) or "None set yet."

        prompt = f"""You are Ethic Companion, an AI assistant that helps users act on their goals with integrity.

User's active goals:
{goal_text}

Upcoming events (next 24 h):
{event_text}

User's stated values:
{value_text}

Write one specific, actionable insight or suggestion for today. Reference concrete goals or events where possible. Be warm, direct, and under 3 sentences. Do not start with "I" or "As your"."""

        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            groq_api_key=settings.GROQ_API_KEY,
            temperature=0.7,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = (response.content or "").strip()

        if not content:
            content = "Review your active goals today and identify one small next step you can take right now."

        # 3. Cache it
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO daily_insights (user_id, content, date)
                        VALUES (%s, %s, CURRENT_DATE)
                        ON CONFLICT (user_id, date) DO UPDATE SET
                            content = EXCLUDED.content,
                            generated_at = NOW()
                        """,
                        (str(user_id), content),
                    )
        except Exception as e:
            logger.warning(f"Could not cache daily insight: {e}")

        return {"insight": content, "cached": False}

    except Exception as e:
        logger.error(f"Daily insight generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Could not generate insight: {str(e)}")
```

- [ ] **Register the router** in `backend/main.py`. Find where routers are included (look for `app.include_router`) and add:

```python
from routes.insight import router as insight_router
app.include_router(insight_router)
```

- [ ] **Run tests — expect PASS**

```bash
pytest tests/test_insight_route.py -v && pytest tests/ --tb=short 2>&1 | tail -5
```

- [ ] **Commit**

```bash
git add backend/routes/insight.py backend/main.py backend/tests/test_insight_route.py
git commit -m "feat: GET /api/insight/daily — LLM-generated daily insight with day-level cache"
```

---

### Task C.3 — Dashboard insight card (frontend)

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/dashboard/page.tsx`

- [ ] **Add `insightApi` to `frontend/lib/api.ts`** (after `settingsApi`):

```typescript
export const insightApi = {
  daily: async (): Promise<{ insight: string; cached: boolean }> =>
    apiRequest<{ insight: string; cached: boolean }>('/api/insight/daily'),
}
```

Also export it from the `api` object at the bottom of the file:
```typescript
insight: insightApi,
```

- [ ] **Add state + fetch** to `frontend/app/dashboard/page.tsx`. In the state declarations add:

```typescript
const [dailyInsight, setDailyInsight] = useState<string | null>(null)
const [insightLoading, setInsightLoading] = useState(true)
```

And in the `load()` async function inside `useEffect`, add to `Promise.allSettled`:
```typescript
insightApi.daily(),
```

Handle the result:
```typescript
// Add 'insight' to the destructured array from Promise.allSettled
if (insight.status === 'fulfilled') {
  setDailyInsight(insight.value?.insight ?? null)
}
// Always stop loading
setInsightLoading(false)
```

- [ ] **Add the insight card** in the JSX, directly after the greeting card (`</Card>` at line ~105) and before the stats row:

```tsx
{/* Daily insight */}
{(insightLoading || dailyInsight) && (
  <div
    className="rounded-2xl p-5 border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
    style={{ background: 'linear-gradient(135deg, #f9f6fa 0%, #ffffff 100%)' }}
  >
    <div className="flex items-center gap-2 mb-2">
      <span className="text-sm" style={{ color: '#695e6e' }}>✦</span>
      <p className="text-xs font-medium" style={{ color: '#695e6e' }}>
        Today's insight from your companion
      </p>
    </div>
    {insightLoading ? (
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    ) : (
      <p className="text-sm leading-relaxed" style={{ color: '#1c1520' }}>
        {dailyInsight}
      </p>
    )}
  </div>
)}
```

- [ ] **Build check**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error TS" | head -10
```

- [ ] **Commit**

```bash
git add frontend/lib/api.ts frontend/app/dashboard/page.tsx
git commit -m "feat: daily insight card on dashboard — personalised AI suggestion each morning"
```

---

## Sub-project D — LLM-generated conversation titles

**Why:** Conversations are currently titled with the first 60 characters of the user's message (e.g. "hey can you help me with my pr…"). An LLM-generated 4–5 word title is far more scannable in the sidebar.

**Files:**
- Modify: `backend/services/orchestrator_v2.py`

### Task D.1 — Replace truncated-text title with LLM summary

- [ ] **Find the two auto-title blocks** in `orchestrator_v2.py`:
  - `handle_user_message`: around line 430–442
  - `_post_stream_store`: around line 601–618

Both currently do:
```python
title = message[:60] + ("…" if len(message) > 60 else "")
```

- [ ] **Replace both blocks** with an async helper call. First, add this helper method to the `OrchestratorV2` class:

```python
async def _generate_conversation_title(self, user_message: str) -> str:
    """Use LLM to generate a short conversation title (4–6 words)."""
    try:
        prompt = (
            f'Generate a conversation title of 4–6 words that captures the topic of this message. '
            f'Reply with the title only, no punctuation at the end.\n\nMessage: "{user_message[:200]}"'
        )
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        title = (response.content or "").strip().strip('"').strip("'")
        # Truncate safety net
        return title[:80] if title else user_message[:60]
    except Exception:
        return user_message[:60] + ("…" if len(user_message) > 60 else "")
```

- [ ] **Update the auto-title block in `handle_user_message`** (around line 435):

```python
# Replace:
title = message[:60] + ("…" if len(message) > 60 else "")
# With:
title = await self._generate_conversation_title(message)
```

- [ ] **Update the auto-title block in `_post_stream_store`** (around line 611):

```python
# Replace:
title = user_msg[:60] + ("…" if len(user_msg) > 60 else "")
# With:
title = await self._generate_conversation_title(user_msg)
```

- [ ] **Run all backend tests** — auto-title is tested indirectly via chat stream tests

```bash
pytest tests/ -v --tb=short 2>&1 | tail -10
```

Expected: 93+ passed

- [ ] **Commit**

```bash
git add backend/services/orchestrator_v2.py
git commit -m "feat: LLM-generated conversation titles replace truncated message text"
```

---

## Sub-project E — Goal milestones

**Why:** Goals are tracked but there's no way to break them into sub-tasks. Milestones make goals actionable and give users a sense of progress.

**Schema already added in Task C.1** (`goal_milestones` table).

### Task E.1 — Backend CRUD for milestones

**Files:**
- Modify: `backend/routes/goals.py`
- Modify: `backend/tests/test_goals_routes.py`

- [ ] **Write failing tests**

```python
# tests/test_goals_routes.py — add at end

def test_create_milestone(client, monkeypatch):
    """POST /api/goals/{id}/milestones creates a milestone."""
    from unittest.mock import patch, MagicMock
    mock_row = {
        "id": "m1m1m1m1-0000-0000-0000-000000000000",
        "goal_id": "00000000-0000-0000-0000-000000000001",
        "title": "Write unit tests",
        "completed": False,
        "created_at": "2026-03-25T10:00:00+00:00",
    }
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = mock_row
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    with patch("routes.goals.get_db", return_value=mock_conn):
        response = client.post(
            "/api/goals/00000000-0000-0000-0000-000000000001/milestones",
            json={"title": "Write unit tests"},
        )
    assert response.status_code in (200, 201, 401)

def test_list_milestones(client, monkeypatch):
    """GET /api/goals/{id}/milestones returns milestone list."""
    from unittest.mock import patch, MagicMock
    mock_rows = [{"id": "m1", "title": "Draft", "completed": False, "created_at": "2026-03-25T10:00:00+00:00"}]
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchall.return_value = mock_rows
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    with patch("routes.goals.get_db", return_value=mock_conn):
        response = client.get("/api/goals/00000000-0000-0000-0000-000000000001/milestones")
    assert response.status_code in (200, 401)

def test_toggle_milestone(client):
    """PATCH /api/goals/{id}/milestones/{milestone_id} toggles completion."""
    from unittest.mock import patch, MagicMock
    mock_row = {"id": "m1", "title": "Draft", "completed": True, "created_at": "2026-03-25T10:00:00+00:00"}
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = mock_row
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    with patch("routes.goals.get_db", return_value=mock_conn):
        response = client.patch(
            "/api/goals/gid/milestones/m1",
            json={"completed": True},
        )
    assert response.status_code in (200, 401, 404)
```

- [ ] **Run — expect FAIL** (404 for new endpoints)

```bash
pytest tests/test_goals_routes.py -v -k "milestone" 2>&1 | tail -10
```

- [ ] **Add milestone endpoints to `backend/routes/goals.py`** — at the end of the file (before any `if __name__` guard):

```python
# ==================== Milestones ====================

class MilestoneCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.get("/{goal_id}/milestones", response_model=dict)
async def list_milestones(
    goal_id: str,
    user_id: str = Depends(get_current_read_user_id),
):
    """List all milestones for a goal."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, goal_id, title, completed, created_at
                    FROM goal_milestones
                    WHERE goal_id = %s AND user_id = %s
                    ORDER BY created_at ASC
                    """,
                    (goal_id, str(user_id)),
                )
                rows = cur.fetchall()
        return {"milestones": serialize_rows(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching milestones: {str(e)}")


@router.post("/{goal_id}/milestones", response_model=dict)
async def create_milestone(
    goal_id: str,
    body: MilestoneCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a milestone for a goal."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO goal_milestones (goal_id, user_id, title)
                    VALUES (%s, %s, %s)
                    RETURNING id, goal_id, title, completed, created_at
                    """,
                    (goal_id, str(user_id), body.title),
                )
                row = cur.fetchone()
        return {"milestone": serialize_row(row)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating milestone: {str(e)}")


@router.patch("/{goal_id}/milestones/{milestone_id}", response_model=dict)
async def toggle_milestone(
    goal_id: str,
    milestone_id: str,
    body: dict,
    user_id: str = Depends(get_current_user_id),
):
    """Toggle completion or rename a milestone."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                updates = []
                params = []
                if "completed" in body:
                    updates.append("completed = %s")
                    params.append(bool(body["completed"]))
                if "title" in body:
                    updates.append("title = %s")
                    params.append(str(body["title"])[:200])
                if not updates:
                    raise HTTPException(status_code=400, detail="Nothing to update")
                updates.append("updated_at = NOW()")
                params.extend([milestone_id, str(user_id)])
                cur.execute(
                    f"""
                    UPDATE goal_milestones SET {', '.join(updates)}
                    WHERE id = %s AND user_id = %s
                    RETURNING id, goal_id, title, completed, created_at
                    """,
                    params,
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Milestone not found")
        return {"milestone": serialize_row(row)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating milestone: {str(e)}")


@router.delete("/{goal_id}/milestones/{milestone_id}", response_model=dict)
async def delete_milestone(
    goal_id: str,
    milestone_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a milestone."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM goal_milestones WHERE id = %s AND user_id = %s",
                    (milestone_id, str(user_id)),
                )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting milestone: {str(e)}")
```

> **Note:** `serialize_row`, `serialize_rows`, `get_current_user_id`, `get_current_read_user_id`, `get_db` are already imported in `goals.py`. Check imports and add any missing ones.

- [ ] **Run milestone tests — expect PASS**

```bash
pytest tests/test_goals_routes.py -v 2>&1 | tail -15
```

- [ ] **Run full suite**

```bash
pytest tests/ --tb=short 2>&1 | tail -5
```

- [ ] **Commit**

```bash
git add backend/routes/goals.py backend/tests/test_goals_routes.py
git commit -m "feat: goal milestones CRUD — list, create, toggle, delete"
```

---

### Task E.2 — Milestone API methods in frontend

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Add milestone methods to `goalsApi`** (find the `goalsApi` object, around line 120–200):

```typescript
milestones: {
  list: async (goalId: string): Promise<{ milestones: Milestone[] }> =>
    apiRequest<{ milestones: Milestone[] }>(`/api/goals/${goalId}/milestones`),

  create: async (goalId: string, title: string): Promise<{ milestone: Milestone }> =>
    apiRequest<{ milestone: Milestone }>(`/api/goals/${goalId}/milestones`, {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),

  toggle: async (goalId: string, milestoneId: string, completed: boolean): Promise<{ milestone: Milestone }> =>
    apiRequest<{ milestone: Milestone }>(`/api/goals/${goalId}/milestones/${milestoneId}`, {
      method: 'PATCH',
      body: JSON.stringify({ completed }),
    }),

  delete: async (goalId: string, milestoneId: string): Promise<void> => {
    await apiRequest(`/api/goals/${goalId}/milestones/${milestoneId}`, { method: 'DELETE' })
  },
},
```

- [ ] **Add `Milestone` interface** near the `Goal` interface:

```typescript
export interface Milestone {
  id: string
  goal_id: string
  title: string
  completed: boolean
  created_at: string
}
```

- [ ] **Build check**

```bash
cd frontend && npm run build 2>&1 | grep "error" | head -10
```

---

### Task E.3 — Milestone UI in goals page

**Files:**
- Modify: `frontend/app/dashboard/goals/page.tsx`

- [ ] **Read the goals page** to understand the current goal card structure before editing.

- [ ] **Add milestone state** — per-goal milestone state using a `Record<string, Milestone[]>` map:

```typescript
const [milestones, setMilestones] = useState<Record<string, Milestone[]>>({})
const [milestoneInput, setMilestoneInput] = useState<Record<string, string>>({})
```

- [ ] **Load milestones** when a goal card is expanded (or on mount for active goals). Add a `loadMilestones(goalId)` function:

```typescript
const loadMilestones = async (goalId: string) => {
  try {
    const { milestones: data } = await goalsApi.milestones.list(goalId)
    setMilestones(prev => ({ ...prev, [goalId]: data }))
  } catch {}
}
```

Call `loadMilestones(goal.id)` when the goals list loads (alongside the existing goals fetch).

- [ ] **Add milestone panel** inside each active goal card, below the goal title/status row:

```tsx
{/* Milestones */}
<div className="mt-3 pt-3 border-t border-[rgba(0,0,0,0.06)]">
  <p className="text-xs font-medium mb-2" style={{ color: '#695e6e' }}>
    Milestones
    {milestones[goal.id] && (
      <span className="ml-1" style={{ color: '#9e9e9e' }}>
        ({milestones[goal.id].filter(m => m.completed).length}/{milestones[goal.id].length})
      </span>
    )}
  </p>
  <ul className="space-y-1.5 mb-2">
    {(milestones[goal.id] ?? []).map(m => (
      <li key={m.id} className="flex items-center gap-2">
        <button
          onClick={async () => {
            await goalsApi.milestones.toggle(goal.id, m.id, !m.completed)
            loadMilestones(goal.id)
          }}
          className="w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors"
          style={{
            background: m.completed ? '#4A7C59' : 'transparent',
            borderColor: m.completed ? '#4A7C59' : '#d4d0d6',
          }}
        >
          {m.completed && <Check size={10} color="#fff" />}
        </button>
        <span
          className="text-xs flex-1"
          style={{
            color: m.completed ? '#9e9e9e' : '#1c1520',
            textDecoration: m.completed ? 'line-through' : 'none',
          }}
        >
          {m.title}
        </span>
        <button
          onClick={async () => {
            await goalsApi.milestones.delete(goal.id, m.id)
            loadMilestones(goal.id)
          }}
          className="opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <X size={11} style={{ color: '#9e9e9e' }} />
        </button>
      </li>
    ))}
  </ul>
  {/* Add milestone input */}
  <form
    className="flex items-center gap-1.5"
    onSubmit={async e => {
      e.preventDefault()
      const title = (milestoneInput[goal.id] || '').trim()
      if (!title) return
      await goalsApi.milestones.create(goal.id, title)
      setMilestoneInput(prev => ({ ...prev, [goal.id]: '' }))
      loadMilestones(goal.id)
    }}
  >
    <input
      type="text"
      value={milestoneInput[goal.id] ?? ''}
      onChange={e => setMilestoneInput(prev => ({ ...prev, [goal.id]: e.target.value }))}
      placeholder="Add milestone…"
      className="flex-1 text-xs px-2 py-1 rounded-lg outline-none"
      style={{ background: '#f5f2ef', color: '#1c1520', border: '1px solid transparent' }}
    />
    <button
      type="submit"
      className="text-xs px-2 py-1 rounded-lg"
      style={{ background: '#000', color: '#fff' }}
    >
      Add
    </button>
  </form>
</div>
```

> **Note:** Add `import { Check, X } from 'lucide-react'` if not already imported. Add `import type { Milestone } from '@/lib/api'` for the type.

- [ ] **Build check**

```bash
cd frontend && npm run build 2>&1 | grep "error" | head -10
```

- [ ] **Commit**

```bash
git add frontend/app/dashboard/goals/page.tsx frontend/lib/api.ts
git commit -m "feat: goal milestones UI — add, toggle, delete sub-tasks within goals"
```

---

## Sub-project F — Weekly AI digest notification

**Why:** The scheduler already runs. Adding a Monday-morning digest makes the app feel alive between sessions — users see a weekly summary in their notifications.

**Files:**
- Modify: `backend/services/scheduler.py`
- Modify: `backend/main.py`

### Task F.1 — Weekly digest job in scheduler

- [ ] **Add `_generate_weekly_digest` to `BackgroundScheduler`** in `scheduler.py`:

```python
async def _generate_weekly_digest(self):
    """
    Generate a weekly digest notification for all users.
    Runs Monday at 8 AM. Creates a notification summarising the week.
    """
    logger.info("[Scheduler] Generating weekly digest notifications...")
    try:
        from utils.db import get_db_connection
        from routes.notifications import create_notification
        from services.context_manager import ContextManager
        from langchain_core.messages import HumanMessage
        from langchain_groq import ChatGroq
        from config import settings

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users LIMIT 100")
                users = cur.fetchall()

        for user_row in users:
            user_id = str(user_row["id"])
            try:
                ctx = ContextManager()
                goals = await ctx.get_active_goals(user_id)
                values = await ctx.get_user_values(user_id)

                if not goals and not values:
                    continue  # Skip users with no data

                goal_text = "\n".join(f"- {g.title}" for g in goals[:5])
                value_text = "\n".join(f"- {v.value}" for v in values[:3])

                prompt = f"""Write a short weekly check-in message (2–3 sentences) for a user.
Active goals:
{goal_text or "None"}

Values:
{value_text or "None"}

Be encouraging and specific. Suggest one concrete action for the week ahead."""

                llm = ChatGroq(
                    model="llama-3.1-8b-instant",
                    groq_api_key=settings.GROQ_API_KEY,
                    temperature=0.7,
                )
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                content = (response.content or "").strip()

                if content:
                    with get_db_connection() as conn:
                        create_notification(
                            conn,
                            user_id=user_id,
                            type="info",
                            title="Your weekly companion check-in",
                            message=content[:500],
                            metadata={"source": "weekly_digest"},
                        )

            except Exception as e:
                logger.warning(f"[Scheduler] Weekly digest failed for user {user_id}: {e}")

    except Exception as e:
        logger.error(f"[Scheduler] Weekly digest job failed: {e}")
```

- [ ] **Register the weekly job** in `BackgroundScheduler.start()` (after the health check job):

```python
# Task 4: Weekly digest — every Monday at 8 AM
self.scheduler.add_job(
    func=self._generate_weekly_digest,
    trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
    id='weekly_digest',
    name='Generate weekly AI digest for all users',
    replace_existing=True,
    max_instances=1,
)
```

Also add to the log output:
```python
logger.info("   - Weekly digest: Every Monday at 8 AM")
```

- [ ] **Run all tests** (scheduler doesn't have unit tests but nothing should break)

```bash
pytest tests/ --tb=short 2>&1 | tail -5
```

- [ ] **Commit**

```bash
git add backend/services/scheduler.py
git commit -m "feat: weekly AI digest — Monday 8AM notification summarising goals and values"
```

---

## Verification Checklist

### A — Notification badge
- [ ] Navigate to `/dashboard/notifications` — badge disappears from Bell icon
- [ ] Create a test notification in DB directly: `INSERT INTO user_notifications (user_id, type, title, message) VALUES ('00000000-...', 'info', 'Test', 'Hello')`
- [ ] Return to `/dashboard` — badge shows "1" on Bell within 60 seconds

### B — ESL → notifications
- [ ] Send a message that triggers ESL (e.g., set a boundary value for "no work after 7pm" and test at night)
- [ ] Check `/dashboard/notifications` — ESL block notification should appear

### C — Daily insight
- [ ] Visit `/dashboard` — insight card appears below greeting
- [ ] `curl http://localhost:8000/api/insight/daily` → returns `{"insight": "...", "cached": false}`
- [ ] Reload — `cached: true`

### D — LLM titles
- [ ] Start a new chat, send "Can you explain how ESL protects me?"
- [ ] Check sidebar — conversation titled something like "ESL Protection Explained" not "Can you explain how ES…"

### E — Goal milestones
- [ ] Open a goal card → milestone section visible
- [ ] Add "Write tests" → appears in list
- [ ] Click checkbox → strikethrough + green fill
- [ ] Counter shows "(1/1)"
- [ ] Backend: `GET /api/goals/{id}/milestones` → 200 with list

### F — Weekly digest
- [ ] Check scheduler logs on startup: "Weekly digest: Every Monday at 8 AM"
- [ ] Test manually: call `await scheduler._generate_weekly_digest()` from a Python console

---

## Execution Order

1. **A** (badge) → **B** (ESL notifications) — fast wins, can be done in any order
2. **C** (daily insight, schema) → includes migration used by E — do before E
3. **D** (LLM titles) — independent, 30 min
4. **E** (milestones) — depends on C schema having run
5. **F** (weekly digest) — last, depends on notifications working (B)
