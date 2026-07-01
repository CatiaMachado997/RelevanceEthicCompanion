# Sprint C — Agentic Workspace Unification

Date: 2026-04-27
Status: Plan
Predecessors: Sprint A (RAG/citations) ✅, Sprint B (Connectors) ✅, Sprint D (Work Mgmt) ✅
This is the final pillar of the original 7-phase master roadmap.

## Goal

Three things:

1. **Multi-step planner.** The agent can plan → execute → observe → re-plan in one chat turn. Today's LangGraph runs `tool_planner` once, executes whatever it produced, and exits. Sprint C adds a loop so the agent can chain (e.g. `search_documents` → `get_user_goals` → `create_note`) within one turn, with per-step ESL gating intact.

2. **Proactive flows actually pass through ESL.** Today's scheduler writes morning brief, pre-meeting brief, and deadline warnings *directly to notifications* — bypassing ESL. That violates `CLAUDE.md`'s "ESL is mandatory" rule. Sprint C wraps every proactive notification in `esl.evaluate_action(...)` and respects veto/modify outcomes.

3. **Unified tool-call telemetry.** Today tool audits are scattered: marketplace tools land in `esl_audit_log`, built-in tools and scheduled jobs aren't recorded at all. Sprint C adds a single `tool_call_events` table populated from both chat turns and scheduled flows, with a transparency drill-down UI.

## Architecture decisions

- **Plan loop, capped depth.** Add a `replan` edge from `tool_execution` back to `tool_planner` with a `max_planner_steps=3` cap on `AgentState`. Agent decides whether to re-plan by emitting another tool call; an empty tool-call list ends the loop. The cap is a hard kill-switch, not a soft hint — prevents tool loops from hanging the chat.
- **ESL gate stays per-tool + per-turn**, unchanged for chat. Adding the loop means `esl_gateway_node` runs *once at the end* on the synthesized response (same as today). Per-tool ESL gates (marketplace tools) fire each iteration as they do now.
- **Proactive ESL: a thin wrapper, not a refactor.** New helper `services/proactive_gate.py::gate_proactive_notification(user_id, notification_type, content, urgency, metadata)` that:
  1. Builds `ProposedAction(action_type=PUSH_NOTIFICATION, content_type=notification_type, ...)`.
  2. Awaits `esl.evaluate_action(...)`.
  3. Returns `(should_send: bool, content: str)` — content may be modified by ESL.
  4. Logs the decision via existing `ESLAuditLogger`.
  Each scheduler flow calls this before `create_notification(...)`. No business logic changes.
- **Tool telemetry: append-only.** New `tool_call_events` table (Postgres). Both `tool_execution_node` and scheduler-side LLM tool calls write a row per tool. No update path. No retention policy this sprint — defer to ops.
- **Transparency drill-down: read-only addition.** Existing transparency page keeps its ESL chart; Sprint C adds a "Tool calls" tab that lists from `tool_call_events`.

## North-star UX

1. User asks "What did I commit to in last week's emails about the migration?" → agent runs `search_documents` (RAG over Gmail content) → reads chunks → runs `get_user_goals` to align with stated priorities → writes a synthesized answer with citations. All in one turn.
2. Monday 8 AM: scheduler triggers daily focus plan. ESL evaluates "push notification: daily plan" against user values — if the user has a "no notifications before 9 AM" boundary, ESL vetoes and the brief is silently dropped (audited, not sent). Today this brief sends regardless.
3. User opens Transparency → "Tool calls" tab → sees 14 tool invocations from the last 24h: `search_documents (240ms)`, `query_calendar (80ms)`, `pre_meeting_brief.daily_focus_plan (LLM 1.4s, ESL APPROVED)`. Click any row → see input/output JSON.

## File map

### Backend

**New:**
- `backend/migrations/012_tool_call_events.sql` — `tool_call_events` table.
- `backend/services/tool_telemetry.py` — `record_tool_call(...)` + query helpers.
- `backend/services/proactive_gate.py` — `gate_proactive_notification(...)` wrapper.
- `backend/tests/test_proactive_gate.py` — 4 tests (approved → sends, vetoed → drops, modified → sends modified content, audit row written).
- `backend/tests/test_tool_telemetry.py` — 3 tests (insert, query by user, query by tool name).
- `backend/tests/test_planner_loop.py` — 4 tests (single-tool turn unchanged, two-tool sequential turn, max-step cap kills loop, empty tool-call list exits loop).

**Modified:**
- `backend/orchestrator/state.py` — add `planner_step: int = 0` and `max_planner_steps: int = 3`.
- `backend/orchestrator/graph.py` — add conditional edge `tool_execution → tool_planner` when more tool calls expected, else → `esl_gateway`.
- `backend/orchestrator/nodes/tools.py` — increment `planner_step` each iteration, surface telemetry call after each tool runs.
- `backend/services/scheduler.py`:
  - `_generate_daily_focus_plan` — gate via `proactive_gate`.
  - `_generate_pre_meeting_briefs` — gate via `proactive_gate`.
  - `_generate_deadline_warnings` — gate via `proactive_gate`.
  - `_generate_weekly_digest` — gate via `proactive_gate`.
  - `_generate_related_items_clusters` — gate via `proactive_gate`.
  - `_generate_project_status_snapshot` — gate via `proactive_gate`.
- `backend/routes/transparency.py` — `GET /api/transparency/tool-calls` with filters.
- `backend/tests/test_proactive_scheduler.py` — extend existing tests so they verify ESL gate is consulted; add veto-respected tests.

### Frontend

**New:**
- `frontend/components/transparency/ToolCallsTab.tsx` — list + drill-down panel.

**Modified:**
- `frontend/app/dashboard/transparency/page.tsx` — add tabs (existing audit log + new "Tool calls").
- `frontend/lib/api.ts` — `transparencyApi.listToolCalls(...)` + `ToolCallEvent` type.

## Tasks (one commit each, TDD where it has a return value to assert)

### 1. Migration: `tool_call_events` table.
Columns:
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
tool_name       TEXT NOT NULL,
source          TEXT NOT NULL,                 -- 'chat' | 'scheduled'
source_ref      TEXT,                          -- conversation_id or job_name
input           JSONB NOT NULL DEFAULT '{}'::jsonb,
output          JSONB,                          -- nullable on early failure
status          TEXT NOT NULL,                 -- 'success' | 'error' | 'vetoed' | 'pending_confirmation'
error_message   TEXT,
esl_decision    TEXT,                          -- 'APPROVED' | 'MODIFIED' | 'VETOED' | NULL
latency_ms      INTEGER,
created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
```
Indexes: `(user_id, created_at DESC)`, `(tool_name, created_at DESC)`.
Idempotent (`IF NOT EXISTS`).

### 2. `tool_telemetry` service + tests.
- `record_tool_call(user_id, tool_name, source, source_ref, input, output, status, error_message, esl_decision, latency_ms) -> str` — returns event UUID.
- `list_tool_calls(user_id, *, tool_name=None, source=None, since=None, limit=50)` — for the transparency drill-down.
- 3 tests using mocked DB cursor.

### 3. `proactive_gate` service + tests.
- `async def gate_proactive_notification(user_id, notification_type, content, urgency, metadata) -> tuple[bool, str]` — returns `(should_send, final_content)`.
- Builds `ProposedAction`, awaits `esl.evaluate_action`, dispatches based on `decision.status`. Logs via `ESLAuditLogger` (already wired through `evaluate_action`, but verify the audit fires for `PUSH_NOTIFICATION` action type).
- 4 tests using mocked ESL: APPROVED, VETOED, MODIFIED (returns modified text), service error (fail-closed → returns `(False, content)`).

### 4. Scheduler proactive flows pass through `proactive_gate`.
- Wrap each of: `_generate_daily_focus_plan`, `_generate_pre_meeting_briefs`, `_generate_deadline_warnings`, `_generate_weekly_digest`, `_generate_related_items_clusters`, `_generate_project_status_snapshot`.
- After LLM produces brief content but before `create_notification`, call the gate. If `should_send=False`, skip the notification (still record in audit — already handled by the gate).
- Each scheduler call also writes a `tool_call_events` row with `source='scheduled'`, `source_ref='<job_name>'`, the LLM input/output as `input`/`output`, and the gate decision as `esl_decision`.
- Extend existing `test_proactive_scheduler.py` tests + add veto-respected cases. **All existing tests must keep passing** — bring in mock ESL where needed.

### 5. AgentState planner-loop fields.
- `planner_step: int = 0`, `max_planner_steps: int = 3` on `AgentState`.
- No tests yet — covered by Task 7.

### 6. `tool_execution_node` records telemetry.
- Around each tool invocation: capture `t0`, run, capture `t1`, call `tool_telemetry.record_tool_call(...)` with `source='chat'`, `source_ref=conversation_id`, `latency_ms=int((t1-t0)*1000)`, `esl_decision` from any per-tool ESL gate that fired (else `None`).
- 1 test asserting telemetry call fires per tool.

### 7. LangGraph plan-loop edge.
- After `tool_execution_node`, the conditional router checks: did the planner emit *new* tool calls in this iteration? If yes AND `planner_step < max_planner_steps`, route back to `tool_planner_node`. Else → `esl_gateway`.
- `tool_planner_node` increments `planner_step` each call.
- 4 tests in `test_planner_loop.py`:
  - single-tool turn behaves identically to today
  - planner emits a tool, observes result, emits a second tool, then no more → final response uses both results
  - planner keeps emitting tools → caps at `max_planner_steps`
  - planner emits zero tool calls on first try → `esl_gateway` fires immediately (today's behaviour preserved)

### 8. Transparency route + frontend tab.
- `GET /api/transparency/tool-calls?tool_name=&source=&since=&limit=` returns `{events: ToolCallEvent[]}`.
- 1 route test.
- `ToolCallsTab` component: simple table (time, tool, source, status, latency, ESL decision) with a side panel that shows pretty-printed input/output JSON when a row is selected.
- Tabs in `transparency/page.tsx`: existing content under "ESL decisions", new under "Tool calls".
- Frontend typecheck must pass.

### 9. Full backend suite + frontend typecheck.
`pytest --tb=short -q` ; `cd frontend && npx tsc --noEmit`.

## Verification

```bash
# Backend
cd backend
pytest tests/test_proactive_gate.py tests/test_tool_telemetry.py tests/test_planner_loop.py -v
pytest tests/test_proactive_scheduler.py -v
pytest --tb=short -q

# Frontend
cd frontend
npx tsc --noEmit
```

**Manual checklist:**
1. In chat, ask a question that requires sequential tools (e.g., "Find tasks linked to the goal I mentioned last week and summarize their state"). Verify multi-tool sequence in transparency log.
2. Add a `time_window` boundary value: "no notifications between 22:00–08:00". Wait for the scheduled daily focus plan to fire at 8 AM with the boundary still in effect — verify no notification appears, and an audit row with `decision_status=VETOED` is recorded.
3. Open Transparency → "Tool calls" tab. See entries for both the chat session and the scheduled job. Click one to see input/output.
4. Verify the existing single-tool flow (e.g., a simple `/ask` query) is identical in latency — no regression from the loop wiring.

## ESL impact summary

| Change | ESL surface |
|---|---|
| Plan loop (chat) | No change — `esl_gateway` still runs once on synthesized response. Per-tool gates already fire today. |
| Proactive flows | **Now pass through ESL.** Closes a real CLAUDE.md violation. |
| Telemetry | Read/write of internal events — not user-facing — no ESL gate. |

## Out of scope / deferred

- **Re-planning based on tool failure.** The loop replans on success only. Failure handling (retry vs. abort) deferred — current behaviour preserved.
- **Token-budget caps** on the loop (separate from `max_planner_steps`). Today's per-turn budget already truncates context; that's enough.
- **Tool-call retention/archive policy.** Telemetry table grows unbounded this sprint. Add a retention job in a future ops sprint.
- **Per-tool latency/error dashboards.** The drill-down lists raw events; aggregation comes later.
- **Notification preferences UI** (let user opt out of specific brief types). Today the only knob is values/boundaries via ESL — that's enough for this sprint.

## Open questions deferred to execution

- **Should `proactive_gate` log to `tool_call_events` AND `esl_audit_log`?** Plan says yes — the audit log captures the ESL decision, the telemetry table captures the LLM call that produced the content. Different shapes, both useful.
- **Failure mode of `proactive_gate` on ESL exception.** Plan says fail-closed (don't send). Acceptable trade-off: a broken ESL service silences proactive notifications; matches "trust over engagement" philosophy.
