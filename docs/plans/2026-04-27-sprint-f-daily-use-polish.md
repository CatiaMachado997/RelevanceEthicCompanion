# Sprint F — Daily-use polish: sync visibility, retrieval that works, no annoying surprises

Date: 2026-04-27
Status: Plan
Predecessors: Sprints A–E ✅

## Why this sprint exists

User feedback after running the app for real: "I synced and don't know what happened. When I ask, the agent tries and fails. Today shows no tasks. Typing 'hello' opens a blank new chat. Errors are annoying."

These are five symptoms of one underlying truth: **the integrations look like they work but the data doesn't reach the agent**, and the chat surface has small bugs that erode trust. Sprint B built the connector → indexer → Weaviate pipeline, but `ConnectorIndexer.index()` swallows embedding/Weaviate errors with a warning log (`connector_indexer.py:90-94`) and no test ever proved the full sync→search loop end-to-end. So in production the agent has nothing to retrieve and the user has no way to tell.

This sprint does **not** add a new pillar. It closes the loop between sync and search, and removes daily-use bug noise.

## Goals

1. **Index failures become visible.** Every failed embed/index records its error on the row (`source_items.embedding_status`, `embedding_error`) and emits a telemetry event. The connectors panel shows the count.
2. **Reindex is one click.** New endpoint + button retries `embedding_status != 'completed'` for a source.
3. **End-to-end test the loop.** First test ever that exercises `source_items insert → indexer → search_documents → result returned`.
4. **Today view stops looking dead.** Cross-source widgets pull from indexed connector data with helpful empty states.
5. **Chat "hello" bug fixed.** Typing a plain message in an existing chat sends in that chat.
6. **Error noise pass.** Internal/transient errors stop popping toasts at the user.
7. **Agent reaches for retrieval more.** System prompt + tool description tweak with regression tests.

## Architecture decisions

- **Failure surface on the row, not a side table.** Add `embedding_error TEXT` to `source_items`. Avoids a parallel error log; the row already has `embedding_status` from Sprint B.
- **Reindex is idempotent.** `POST /api/connectors/{source}/reindex` re-runs `_maybe_embed` for items where `embedding_status IN ('failed', 'pending', NULL)`. Caps at 200/run to avoid Weaviate hammering.
- **Today widgets reuse existing endpoints.** No new aggregation service. The page composes `tasks`, `search_documents` (last 24h, scoped), `notifications`, calendar.
- **"Hello" bug** — investigate first, then write minimal fix. Likely lives in chat page routing or slash-command early return.
- **Error pass is a sweep**, not an architecture change. Categorize: actionable / transient / empty-state.
- **Tool-use bias** is prompt + tool-description text only. No graph rewiring.

## Tasks (one commit each)

### 1. Index-failure observability
- Migration `015_source_items_embedding_error.sql` — `ALTER TABLE source_items ADD COLUMN IF NOT EXISTS embedding_error TEXT`.
- `connector_indexer.py` — on exception in `index()`, set `embedding_status='failed'`, write the exception message to `embedding_error`, record `tool_call_events` row (status=error, tool_name=`connector_indexer`, source=`scheduled`, source_ref=connector name).
- `services/data_ingestion.py` — on success, set `embedding_status='completed'` and clear `embedding_error`.
- 2 tests: failure path writes error + status; success path clears error.

### 2. Reindex endpoint + integration test
- `POST /api/connectors/{source}/reindex` — body `{user_id implicit}`, queries `source_items` where `user_id=$1 AND source_type=$2 AND embedding_status != 'completed'`, runs `_maybe_embed` on each (cap 200), returns `{processed, succeeded, failed}`.
- **Integration test** in `tests/test_connector_indexer.py` (or new `test_sync_to_search_loop.py`): insert a `source_items` row → run indexer → query `RagRetrievalService.retrieve()` → assert hit. Mocks Weaviate to round-trip a real chunk write/read.
- 1 route test for reindex.

### 3. Connector status panel UI
- `frontend/app/dashboard/connectors/page.tsx` — per-connector card: last sync time, total items, indexed (`embedding_status='completed'`) count, failed count, last error (if any), "Reindex" button.
- New backend route `GET /api/connectors/{source}/status` returns those counts.
- 1 backend route test, frontend typecheck.

### 4. Fix "hello opens new blank chat" bug
- Reproduce: open existing chat, type "hello", observe what happens.
- Trace: `frontend/app/dashboard/chat/[id]/page.tsx` send handler, slash-command parser. Hypothesis: a regex matches plain text and triggers a "new chat" branch.
- Fix + regression test (frontend or e2e — whichever is cheaper).

### 5. Error noise audit
- Grep `frontend/` for `toast.error`, `toast({ variant: 'destructive' })`, error banners.
- Categorize each: keep (actionable, plain language), demote (console.error only), remove (genuine empty state, render empty UI).
- Single sweep commit. No new components — only edits.

### 6. Today view cross-source widgets
- `frontend/app/dashboard/today/page.tsx` — replace single "no tasks due" with 4 widgets:
  - Tasks due today/overdue (existing)
  - Recent emails indexed (last 24h, from `source_items` where source_type='gmail', status='completed', limit 5)
  - Recent Slack mentions indexed (same shape)
  - Calendar events today (existing if present, else stub with empty state)
- New backend route `GET /api/today/feed` aggregates these (one query per widget, parallel).
- Each widget has an empty state: "Connect Gmail to see this here" with a link to /dashboard/connectors.

### 7. Tool-use bias prompt + planner tests
- Update orchestrator system prompt (in `orchestrator/nodes/planner.py` or wherever the prompt is composed) to nudge retrieval on integration-shaped queries.
- Update `search_documents` tool description in the registry to include sample queries: "what did X say about Y", "find that thing about Z", "summarize discussions about W".
- 3 tests in `test_orchestrator_graph.py` that assert the planner emits a `search_documents` tool call for these query shapes (with a stub LLM that follows instructions).

### 8. Full suite + typecheck + push
- `pytest --tb=short -q`; `cd frontend && npx tsc --noEmit`. Both green.
- Push to `claude/pensive-jemison-645b09`. Update PR #48 body with a Sprint F section.

## Verification

```bash
cd backend
pytest tests/test_connector_indexer.py tests/test_sync_to_search_loop.py -v
pytest --tb=short -q

cd ../frontend
npx tsc --noEmit
```

**Manual checklist:**
1. Sync Gmail (or trigger sync manually) → connectors panel shows "synced N, indexed N, failed 0" within a minute.
2. Force a Weaviate failure → see "failed: <message>" on the panel, click Reindex, observe items move to indexed.
3. Ask the agent "what did the team say about X" where X is in a synced email → answer cites the email.
4. Open Today → see tasks + emails + Slack mentions + calendar (or correct empty states).
5. Open existing chat, type "hello" → message sends in that chat, no new-chat surprise.
6. Trigger a known transient error path → no toast, only console.

## Out of scope

- **Onboarding wizard for new users.** Daily-use polish first.
- **Reranker / retrieval quality.** Once items are reliably indexed.
- **Mobile/responsive.**
- **Per-user retention preferences, alerting on scheduler failures.** Sprint G material.
- **Backfilling already-synced items that failed silently before this sprint.** The reindex button covers it manually.

## Open questions deferred to execution

- Does `source_items` already have `embedding_status` populated correctly for Sprint B-era rows? If not, Task 2's reindex covers them anyway.
- Where is the system prompt actually composed? `orchestrator/nodes/planner.py` is the guess — confirm in execution.
- Frontend test framework — is there one for chat? If not, Task 4 ships without an automated regression test (manual verification only) and we note the gap.
