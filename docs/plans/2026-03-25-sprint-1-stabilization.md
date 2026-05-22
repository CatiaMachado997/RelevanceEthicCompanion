# Sprint 1: Stabilization & Architecture Alignment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current app reliably usable — auth is unambiguous, runtime is stable, feedback/transparency work end-to-end, and the normalized source_items schema is in place as foundation for Sprint 2.

**Architecture:** All changes are additive or cleanup — no new features. The ESL must stay intact throughout. Every backend change that touches the DB must update both `schema.sql` (production) and `schema_local.sql` (local Docker). Auth is standardized on Supabase; Firebase references removed.

**Tech Stack:** FastAPI · PostgreSQL (psycopg3 dict_row) · Weaviate · Supabase Auth · Next.js 15

---

## File Map

| File | Change |
|------|--------|
| `backend/main.py` | Add startup health checks, Weaviate graceful fallback |
| `backend/config.py` | Remove Firebase env vars, add health check flags |
| `backend/utils/health.py` | **Create** — health check helpers for DB + Weaviate + scheduler |
| `backend/routes/health.py` | **Create** — `GET /health` endpoint with component status |
| `backend/database/schema.sql` | Add `source_items` table |
| `backend/database/schema_local.sql` | Add `source_items` table |
| `backend/database/migration_sprint1.sql` | **Create** — adds `source_items` with backward compat |
| `backend/services/context_manager.py` | Add Weaviate-absent fallback path in all semantic methods |
| `backend/routes/feedback.py` | Verify route is wired; ensure response body matches frontend |
| `backend/routes/transparency.py` | Verify ESL audit log populates from real decisions |
| `frontend/app/dashboard/chat/page.tsx` | Verify feedback POST calls real API (not mock) |
| `frontend/app/dashboard/transparency/page.tsx` | Verify transparency data loads from real ESL decisions |
| `README.md` | Rewrite to match current stack/auth/run commands |
| `docs/ARCHITECTURE.md` | **Create** — canonical architecture doc |

---

## Task 1: Architecture Cleanup

**Files:**
- Modify: `README.md`
- Create: `docs/ARCHITECTURE.md`
- Modify: `backend/config.py` (remove Firebase refs)

- [ ] **Step 1: Search for Firebase references in the codebase**

```bash
grep -r "firebase\|Firebase\|FIREBASE" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.md" --include="*.env*" /path/to/repo --exclude-dir=node_modules --exclude-dir=venv -l
```
Expected: a list of files referencing Firebase.

- [ ] **Step 2: Remove Firebase env vars from `backend/config.py`**

Remove any `FIREBASE_*` fields from the `Settings` class. Supabase is the auth provider. Keep `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`.

- [ ] **Step 3: Create `docs/ARCHITECTURE.md`**

```markdown
# Ethic Companion Architecture

## Auth
Supabase Auth (JWT). Backend validates tokens via `utils/supabase_auth.py`.
Dev mode: set `ENVIRONMENT=development` to bypass auth checks (`DEV_USER_ID` used).

## Stack
- Backend: FastAPI (Python 3.11+) on port 8000
- Frontend: Next.js 15 App Router on port 3000
- DB M1: PostgreSQL 15 (local Docker: `backend-db-1`, production: Supabase)
- DB M2: Weaviate (local Docker: `backend-weaviate-1`, optional — app degrades gracefully)
- LLM: Groq API (Llama 3.3 70B default)
- Embeddings: Gemini API (text-embedding-004)
- Search: Tavily API (web search tool)

## Key Services
- `services/orchestrator_v2.py` — main chat orchestration, LangChain tool loop
- `services/context_manager.py` — M1+M2 retrieval, single entry point for context
- `esl/engine.py` — Ethical Safeguard Layer, evaluates all proposed actions
- `services/data_ingestion.py` — OAuth data sync (Calendar, Gmail, Slack)
- `services/feedback_processor.py` — processes thumbs up/down, updates relevance weights

## Domain Entities
UserProfile · UserValue · Goal · Connection · SourceItem · Document
Conversation · ConversationTurn · Task · Insight · FeedbackEvent · TransparencyLog

## Routing
All API routes under `/api/*`. Frontend calls backend via `NEXT_PUBLIC_API_URL`.
Auth token passed as `Authorization: Bearer <token>` header.
```

- [ ] **Step 4: Rewrite README.md top section**

Replace the stale product description and run commands with the current stack. Key sections:
- What is Ethic Companion (one sentence: personal work orchestration assistant, guided by values, protected by ESL)
- Quick start (backend + frontend + Docker)
- Auth setup (Supabase only)
- Link to `docs/ARCHITECTURE.md`

- [ ] **Step 5: Commit**

```bash
git add README.md docs/ARCHITECTURE.md backend/config.py
git commit -m "docs: architecture alignment — remove Firebase refs, add ARCHITECTURE.md"
```

---

## Task 2: Runtime Stabilization

**Files:**
- Create: `backend/utils/health.py`
- Create: `backend/routes/health.py`
- Modify: `backend/main.py`
- Modify: `backend/services/context_manager.py`

- [ ] **Step 1: Create `backend/utils/health.py`**

```python
"""Health check helpers — non-fatal probes for DB, Weaviate, scheduler."""
from utils.db import get_db_connection
from utils.weaviate_client import get_weaviate_client
import logging

logger = logging.getLogger(__name__)


def check_db() -> dict:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        logger.warning(f"DB health check failed: {e}")
        return {"status": "error", "detail": str(e)}


def check_weaviate() -> dict:
    try:
        client = get_weaviate_client()
        if client is None:
            return {"status": "unavailable"}
        client.is_ready()
        return {"status": "ok"}
    except Exception as e:
        logger.warning(f"Weaviate health check failed: {e}")
        return {"status": "unavailable", "detail": str(e)}
```

- [ ] **Step 2: Create `backend/routes/health.py`**

```python
"""GET /health — returns status of all backend dependencies."""
from fastapi import APIRouter
from utils.health import check_db, check_weaviate

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    db = check_db()
    weaviate = check_weaviate()
    overall = "ok" if db["status"] == "ok" else "degraded"
    return {
        "status": overall,
        "components": {
            "database": db,
            "weaviate": weaviate,
        },
    }
```

- [ ] **Step 3: Register health route in `backend/main.py`**

```python
from routes.health import router as health_router
app.include_router(health_router)
```

- [ ] **Step 4: Verify Weaviate fallback in `context_manager.py`**

Check that all methods that use `self.weaviate_client` are guarded:
```python
if self.weaviate_client is None:
    logger.warning("Weaviate unavailable — skipping semantic operation")
    return []  # or appropriate default
```
Every public method must handle `weaviate_client = None` gracefully without raising.

- [ ] **Step 5: Test health endpoint manually**

```bash
# Start backend
cd backend && python main.py &

# With Weaviate running
curl http://localhost:8000/health
# Expected: {"status":"ok","components":{"database":{"status":"ok"},"weaviate":{"status":"ok"}}}

# Stop Weaviate container, re-test
curl http://localhost:8000/health
# Expected: {"status":"degraded","components":{"database":{"status":"ok"},"weaviate":{"status":"unavailable",...}}}
```

- [ ] **Step 6: Commit**

```bash
git add backend/utils/health.py backend/routes/health.py backend/main.py backend/services/context_manager.py
git commit -m "feat: health endpoint + Weaviate-tolerant startup"
```

---

## Task 3: Normalized source_items Schema

**Files:**
- Modify: `backend/database/schema.sql`
- Modify: `backend/database/schema_local.sql`
- Create: `backend/database/migration_sprint1.sql`

This is the foundation for Sprint 2's connector framework. Add the table now so Sprint 2 can write to it without a schema migration.

- [ ] **Step 1: Write the migration file**

Create `backend/database/migration_sprint1.sql`:

```sql
-- Sprint 1: Add source_items normalized table
-- Safe to run multiple times (IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS source_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type     TEXT NOT NULL,           -- 'google_calendar', 'gmail', 'slack', 'upload'
    source_item_type TEXT NOT NULL,          -- 'event', 'email', 'message', 'document'
    external_id     TEXT,                    -- original ID from the source system
    title           TEXT,
    body            TEXT,
    metadata        JSONB DEFAULT '{}',
    item_at         TIMESTAMPTZ,             -- when the item occurred (event start, email sent, etc.)
    synced_at       TIMESTAMPTZ DEFAULT NOW(),
    embedding_status TEXT DEFAULT 'pending', -- 'pending', 'indexed', 'failed'
    sensitivity     INTEGER DEFAULT 0,       -- 0=normal, 1=sensitive, 2=private
    relevance_hints JSONB DEFAULT '{}',
    UNIQUE (user_id, source_type, external_id)
);

CREATE INDEX IF NOT EXISTS idx_source_items_user_source
    ON source_items (user_id, source_type);

CREATE INDEX IF NOT EXISTS idx_source_items_user_item_at
    ON source_items (user_id, item_at DESC);

CREATE INDEX IF NOT EXISTS idx_source_items_embedding_status
    ON source_items (embedding_status)
    WHERE embedding_status = 'pending';
```

- [ ] **Step 2: Add the same table definition to `schema.sql` and `schema_local.sql`**

Both files should contain the `source_items` CREATE TABLE statement in the appropriate section (after `data_sources` or similar).

- [ ] **Step 3: Apply the migration to the local database**

```bash
# Find the postgres container name
docker ps --filter "name=postgres" --format "{{.Names}}"
# Usually: backend-db-1

docker exec -i backend-db-1 psql -U postgres -d ethiccompanion \
  < backend/database/migration_sprint1.sql
```
Expected: `CREATE TABLE` (or `NOTICE: ... already exists` if re-run).

- [ ] **Step 4: Verify the table exists**

```bash
docker exec -it backend-db-1 psql -U postgres -d ethiccompanion \
  -c "\d source_items"
```
Expected: column list matching the migration.

- [ ] **Step 5: Commit**

```bash
git add backend/database/schema.sql backend/database/schema_local.sql backend/database/migration_sprint1.sql
git commit -m "feat: add source_items normalized table (Sprint 2 foundation)"
```

---

## Task 4: Feedback Wiring Validation

**Files:**
- Modify: `backend/routes/feedback.py` (if gaps found)
- Modify: `frontend/app/dashboard/chat/page.tsx` (if gaps found)

- [ ] **Step 1: Check the feedback route response shape**

Read `backend/routes/feedback.py`. The `POST /api/feedback` endpoint must return at minimum `{"status": "ok"}`. The frontend calls it with:
```json
{
  "item_id": "<message_id>",
  "item_type": "chat_response",
  "feedback_type": "thumbs_up" | "thumbs_down"
}
```
Verify the Pydantic model accepts these fields.

- [ ] **Step 2: Check the `feedback_processor.py` DB write**

Read `backend/services/feedback_processor.py`. Confirm it writes to a `feedback_events` or `relevance_adjustments` table. If it writes to a table that doesn't exist, add it to `migration_sprint1.sql` and re-apply.

- [ ] **Step 3: Test feedback end-to-end**

```bash
# Get a valid token first (dev mode: any value works if ENVIRONMENT=development)
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev" \
  -d '{"item_id":"test-123","item_type":"chat_response","feedback_type":"thumbs_up"}'
```
Expected: `{"status":"ok"}` (or similar success response, not 422 or 500).

- [ ] **Step 4: Verify `handleFeedback` in chat page hits real API**

In `frontend/app/dashboard/chat/page.tsx`, find `handleFeedback`. Confirm it calls `api.feedback.submit(...)`. Check `frontend/lib/api.ts` that `feedback.submit` POSTs to `/api/feedback` with the correct payload.

- [ ] **Step 5: Fix any mismatch found**

If `api.feedback.submit` is not implemented or sends wrong fields, update `frontend/lib/api.ts`.

- [ ] **Step 6: Commit any fixes**

```bash
git add backend/routes/feedback.py frontend/lib/api.ts
git commit -m "fix: wire chat feedback to real feedback API"
```

---

## Task 5: Transparency Logs Validation

**Files:**
- Modify: `backend/routes/transparency.py` (if gaps found)
- Modify: `backend/esl/audit.py` (if audit log writes are missing)
- Modify: `frontend/app/dashboard/transparency/page.tsx` (if UI is broken)

- [ ] **Step 1: Check the transparency route**

Read `backend/routes/transparency.py`. It should query the `esl_audit_log` table and return a list of decisions. Confirm it exists and returns data in the expected shape.

- [ ] **Step 2: Check ESL audit writes**

Read `backend/esl/audit.py`. Every ESL decision (APPROVED, VETOED, MODIFIED) must call `audit.log(decision, user_id, ...)`. Confirm the write goes to the `esl_audit_log` table. If the table doesn't exist, verify it's in `schema_local.sql`.

- [ ] **Step 3: Send a chat message and check the audit log**

```bash
# Send a message via the stream endpoint
curl "http://localhost:8000/api/chat/stream?message=hello&model=llama-3.3-70b-versatile" \
  -H "Authorization: Bearer dev"

# Then check audit log
curl http://localhost:8000/api/transparency \
  -H "Authorization: Bearer dev"
```
Expected: at least one entry in the returned list after the chat message.

- [ ] **Step 4: Check the frontend transparency page**

Navigate to `/dashboard/transparency`. Verify the page renders ESL decisions. If it shows an empty state even after a chat, the API call or data mapping is broken.

- [ ] **Step 5: Fix any gaps found**

Common issues:
- Audit log not wired in `esl/engine.py` after decision
- Transparency route filtering by wrong user ID
- Frontend calling wrong endpoint URL

- [ ] **Step 6: Commit any fixes**

```bash
git add backend/esl/audit.py backend/routes/transparency.py
git commit -m "fix: ensure ESL decisions write to audit log and appear in transparency page"
```

---

## Task 6: End-to-End Smoke Test

This is a manual validation checklist. No code changes unless a gap is found.

- [ ] **Auth flow**
  - Visit `http://localhost:3000/login`
  - Sign in with Supabase email/password
  - Confirm redirect to `/dashboard`

- [ ] **Dashboard loads**
  - Dashboard page renders without errors
  - No console errors related to API calls

- [ ] **Integrations page**
  - Visit `/dashboard/integrations`
  - Google Calendar shows as connectable
  - Click "Connect" → redirected to Google OAuth

- [ ] **Calendar sync** (requires Google OAuth completed)
  - After OAuth redirect back, integration shows "Connected"
  - Click Sync — no errors
  - Check backend logs: events appear in `calendar_events` table

- [ ] **Chat with calendar context**
  - Visit `/dashboard/chat`
  - Send: "What's on my calendar today?"
  - Response should reference actual calendar events (if any exist for today)
  - No 500 errors in backend logs

- [ ] **Feedback**
  - After receiving a chat response, click thumbs up
  - Button turns green
  - Backend logs show feedback API call succeeded

- [ ] **Transparency**
  - Visit `/dashboard/transparency`
  - At least one ESL decision entry appears from the chat above

- [ ] **Weaviate down test**
  - `docker stop backend-weaviate-1`
  - Send a chat message
  - Response still works (may lack semantic memory context)
  - No 500 — graceful degradation
  - `docker start backend-weaviate-1`

- [ ] **Commit smoke test result note**

```bash
git commit --allow-empty -m "chore: sprint 1 smoke test complete — [date]"
```

---

## Verification Commands Summary

```bash
# Backend tests
cd backend && pytest tests/test_esl.py -v
cd backend && pytest tests/ -v --tb=short

# Health check
curl http://localhost:8000/health

# Feedback
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" -H "Authorization: Bearer dev" \
  -d '{"item_id":"test","item_type":"chat_response","feedback_type":"thumbs_up"}'

# Transparency
curl http://localhost:8000/api/transparency -H "Authorization: Bearer dev"

# Source items table
docker exec -it backend-db-1 psql -U postgres -d ethiccompanion -c "SELECT COUNT(*) FROM source_items;"

# Frontend build
cd frontend && npm run build
```

---

## Sprint 1 Acceptance Criteria

- [ ] `GET /health` returns component status; app starts even if Weaviate is down
- [ ] No Firebase references in active code
- [ ] `docs/ARCHITECTURE.md` exists and matches current implementation
- [ ] `source_items` table exists in both schema files and local DB
- [ ] Thumbs up/down in chat POSTs to `/api/feedback` and returns success
- [ ] ESL decisions appear in `/dashboard/transparency` after chat
- [ ] All existing ESL tests pass: `pytest tests/test_esl.py -v`
- [ ] Frontend build is clean: `npm run build`
