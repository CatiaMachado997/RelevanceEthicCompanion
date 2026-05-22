# Sprint E — Polish & Ops

Date: 2026-04-27
Status: Plan
Predecessors: Sprints A–D ✅ (Documents, Connectors, Agentic, Work-Mgmt all shipped).

## Why this sprint exists

The four roadmap pillars are done, but each sprint left small follow-ups:

- **Sprint A:** end-to-end smoke test was a runbook, not a script.
- **Sprint B:** goals list endpoint doesn't include `rollup` (frontend falls back to derived progress).
- **Sprint C:** `tool_call_events` grows unbounded; no retention job. No per-tool latency aggregations.
- **Sprint D:** weekly review exists but isn't surfaced as a Monday-morning proactive notification (would close the loop with the Sprint C ESL gate).

This sprint **does not** introduce a new product pillar. It cleans up debt and adds the operational guardrails the system needs now that the feature surface is wide.

## Goals

1. **Retention.** `tool_call_events` and `esl_audit_log` get a daily prune job (default: keep 90 days). Configurable via env.
2. **Observability.** A small "system health" dashboard surface that aggregates the data we already collect: tool-call success rate, p50/p95 latency per tool, ESL veto rate, scheduler job last-run times.
3. **Goals list rollup.** Backend returns `rollup` per-goal in the list endpoint so the frontend stops doing fallback math.
4. **Monday weekly-review notification.** A scheduled job that runs every Monday at user-local 8 AM, generates the weekly-review summary as a notification, and routes through `proactive_gate`. Reuses the Sprint D `WorkRollupsService.get_weekly_review` and the Sprint C ESL gate — no new business logic.
5. **Datetime hygiene.** Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` (the test suite logs ~80 deprecation warnings every run). Mechanical, low-risk, but blocks a clean Python 3.14 upgrade.
6. **Open PR for the entire push.**

## Architecture decisions

- **Retention as a single APScheduler cron job**, not a separate worker. Daily 04:00 UTC. Runs `DELETE … WHERE created_at < NOW() - INTERVAL '%s days'` on both tables in one transaction. Logs row counts.
- **Health dashboard reuses existing tables.** No new persistence. Aggregations are computed on read via SQL views (mirror Sprint D's rollup pattern).
- **Goals list rollup via existing view.** `v_goal_rollup` already exists (Sprint D Task 1). The list endpoint joins to it and inlines per-goal.
- **Monday review uses user timezone** if `users.timezone` exists; otherwise defaults to UTC. Don't add a timezone column this sprint — read what's there, fall back to UTC.
- **datetime hygiene is mechanical** — one regex sweep + targeted edits. No behaviour change. Run full suite afterward.

## Tasks (one commit each)

### 1. Retention migration + job
- New migration `013_retention_indexes.sql` — add `created_at` btree indexes if missing on `tool_call_events` (already there per Sprint C migration) and `esl_audit_log` (verify; add if missing).
- New scheduler job `_prune_old_telemetry` — daily 04:00 UTC. Deletes rows older than `RETENTION_DAYS` (env, default 90) from both tables. Logs `f"pruned {n} tool_call_events, {m} esl_audit_log entries older than {days}d"`.
- Tests: `backend/tests/test_retention.py` — 2 tests using mocked DB cursor (delete count returned, default vs. configured days).

### 2. Health views + service
- Migration `014_system_health_views.sql`:
  - `v_tool_call_health(user_id, tool_name, source, calls_24h, success_rate, p50_latency_ms, p95_latency_ms)` — uses `percentile_cont` over the last 24h.
  - `v_esl_decision_summary(user_id, decision_status, count_24h, count_7d)`.
- Service `backend/services/system_health.py` — `get_tool_health(user_id)`, `get_esl_summary(user_id)`, `get_scheduler_status()` (last-run timestamps from APScheduler — read in-memory, no new persistence).
- Tests: 3 (one per query).

### 3. Health route + frontend
- Route `GET /api/transparency/system-health` returns aggregated dicts.
- New tab "System health" in `frontend/app/dashboard/transparency/page.tsx`. Renders tool latency table, decision summary, scheduler last-run list.
- 1 backend route test, frontend typecheck.

### 4. Goals list rollup
- Modify `GET /api/goals/` (the list endpoint) to LEFT JOIN `v_goal_rollup` and inline `rollup: {...}` on each goal. Match the shape Sprint D Task 5 used for the detail endpoint so the frontend type already covers it.
- Remove the fallback derivation in `frontend/app/dashboard/goals/page.tsx` (Sprint D Task 9 noted this as a known gap).
- 1 backend test (list returns rollup), 1 frontend typecheck pass.

### 5. Monday weekly-review notification
- New scheduler job `_generate_weekly_review_brief` — CronTrigger(day_of_week='mon', hour=7, minute=0, UTC). Per user:
  - Skip if user has no work-management activity this week (no completed_tasks/milestones AND no upcoming).
  - Build content via `WorkRollupsService.get_weekly_review`.
  - Format as a 2–3 sentence summary using the existing LLM helper that other briefs use.
  - **Pass through `gate_proactive_notification`** (Sprint C — already exists). Notification type `"weekly_review_brief"`.
  - On send, also write `tool_call_events` row (consistent with other proactive flows post-Sprint C).
- Tests: extend `test_proactive_scheduler.py` — 2 tests (sends with content; respects veto).

### 6. datetime.utcnow() → datetime.now(timezone.utc)
- Sweep `backend/` for `datetime.utcnow()`. Replace each with `datetime.now(timezone.utc)`. Add `timezone` to imports as needed.
- No behaviour change. Verify by running full suite — should still be 390+ passed, 0 new failures, 0 of the 80 utcnow deprecation warnings.

### 7. Pull request
- Open a PR for `claude/pensive-jemison-645b09` → `main` covering Sprints A, B, C, D, E.
- Title: `Sprints A–E: RAG, connectors, agentic loop, work-management depth, ops polish`
- Body: per-sprint summary + checklist of what each closed.

### 8. Full suite + typecheck
- `pytest --tb=short -q` ; `cd frontend && npx tsc --noEmit`. Both green.

## Verification

```bash
# Backend
cd backend
pytest tests/test_retention.py tests/test_system_health.py -v
pytest tests/test_proactive_scheduler.py -v
pytest --tb=short -q

# Frontend
cd frontend
npx tsc --noEmit
```

**Manual checklist:**
1. Trigger the prune job manually (`scheduler.run_job('_prune_old_telemetry')` if exposed, or wait until 04:00 UTC). Verify old rows are gone, recent rows remain.
2. Open Transparency → System health → see latency p50/p95 per tool, scheduler last-run timestamps.
3. Open Goals page → confirm rollup data renders without "Rollup unavailable" hint.
4. Wait until next Monday 7:00 UTC → verify weekly review notification arrives (or doesn't, if ESL has a quiet-hours boundary).
5. PR opened, review-ready.

## Out of scope

- **User-configurable retention** per-user. One global env var is enough.
- **Telemetry sampling** to reduce volume. Premature optimization until we see the table size.
- **Alerting** when scheduler jobs fail. Logs are enough this sprint.
- **Per-tool dashboards** beyond the latency table. Add them when we know which tools matter.
- **i18n / timezone column on `users`.** Sprint E reads what's there; adding a timezone preferences UI is its own micro-sprint.
- **End-to-end smoke test as a real script.** Still a manual runbook — automating would mean spinning up a test stack with Postgres + Weaviate + mocked OAuth, which is its own project.

## Open questions deferred to execution

- **Index on `tool_call_events.created_at` alone** — Sprint C migration already created `(user_id, created_at DESC)` and `(tool_name, created_at DESC)` composite indexes. The retention DELETE will use one of these efficiently. No new index needed.
- **Should the prune job run inside ESL?** No — it's an internal operational task, not a user-facing action. Same logic that exempts `tool_telemetry.record_tool_call`.
- **`datetime.utcnow()` in test files** — replace there too, or only in `services/`? Replace everywhere; test files emit warnings too.
