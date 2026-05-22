# Sprint I — Explicit ReAct + Parallel Actions

**Date:** 2026-05-20
**Status:** Design
**Predecessors:** Sprints A–H ✅
**Successors planned:** Sprint J (streaming reasoning + interrupts), Sprint K (episodic tool memory)

---

## Why this sprint exists

The orchestrator already runs a ReAct loop today — `tool_planner_node` ↔
`tool_execution_node` ↔ planner again, capped at three iterations
(`max_planner_steps = 3`). Two limitations make it feel weaker than it is:

1. **The "thought" is implicit.** The planner LLM picks a tool but never says
   *why*. There's no narrative the user could read and no trace future
   sprints (J, K) could stream, persist, or learn from.

2. **Only one tool per step.** When a question naturally fans out — e.g.
   "what was that M-KOPA email and was I free that week?" — the planner can
   only call `search_documents`, wait, then call `query_calendar`. The two
   are independent; serial execution is wasted latency.

This sprint makes the ReAct thought explicit and lets a single step fire
multiple independent tool calls in parallel. It does **not** change the
loop topology (planner ↔ executor stays), it does **not** change the
step cap, and it does **not** introduce sub-agents. It's a focused
deepening of the existing loop.

It is also the foundation for Sprints J and K — both need an explicit,
persisted plan trace to render and remember.

---

## Goals

1. **Per-step planner output is structured.** The LLM emits
   `{ thought: string, actions: [tool_call, ...] }`. The empty actions
   list is the loop-terminator.
2. **Independent actions in a step run in parallel.** `asyncio.gather`
   with one auto-retry per failed action, then partial-failure surfaced
   to the planner so the next step can route around the error.
3. **Plans are persisted, queryable, and renderable.** A new
   `planner_runs` table stores the canonical trace per turn;
   `conversation_turns.metadata.plan_steps` keeps a denormalized copy
   for fast chat rendering.
4. **Transparency surfaces step-grouped tool calls.** New "Plan" view
   on the existing tab; legacy rows without a step_index fall back to
   flat view.
5. **No regression in user-visible behavior.** Same final response
   quality, same ESL gating, same citations, same SSE event order to
   the frontend.

---

## Non-goals

- Streaming the thought to the user as it's generated — that's Sprint J.
  This sprint persists the thought; rendering live is the next sprint's
  job.
- Cross-step parallelism (e.g. starting step 2 before step 1 finishes).
  Out of scope; ReAct is sequential between steps by definition.
- Specialist sub-agents (calendar agent, research agent). The planner
  remains one node with one tool registry. Sub-agents would be a
  bigger architectural change we're explicitly deferring.
- Adaptive step cap. Loop cap stays at 3, configurable via
  `MAX_PLANNER_STEPS` env var. We'll revisit after Sprint K when we
  have signal on how often the cap bites.
- Re-running tools whose results are stale or invalidated. Each
  invocation re-fires from scratch; idempotency is the tool's
  problem.

---

## Architecture

### Per-step planner output

The planner LLM is prompted to emit a single JSON object per call:

```json
{
  "thought": "I need to find the M-KOPA email date AND check what was on the calendar that week. The calendar lookup doesn't depend on the email contents, so run both at once.",
  "actions": [
    { "tool": "search_documents", "params": { "query": "M-KOPA Welcome to the Jungle" } },
    { "tool": "query_calendar",   "params": { "days_back": 30 } }
  ]
}
```

The empty-actions form is the only loop-exit signal:

```json
{
  "thought": "I have enough information to answer.",
  "actions": []
}
```

The existing single-tool prompt is rewritten to teach this shape. We
keep a one-line fallback parser: if the LLM emits the legacy
`{ "tool": ..., "params": ... }` shape, treat it as a single-action
step. This lets us roll out without a hard cutover on the prompt.

### Per-step execution

`tool_execution_node` becomes async:

```python
async def tool_execution_node(state: AgentState) -> dict:
    step = state["plan_steps"][-1]
    results = await asyncio.gather(
        *[_execute_with_retry(action) for action in step["actions"]],
        return_exceptions=False,  # _execute_with_retry never raises
    )
    step["observations"] = results
    # ... record each result in tool_call_events with step_index ...
```

`_execute_with_retry` wraps each tool call:

1. Call the tool. If it succeeds → return `{ status: "ok", result, latency_ms, attempts: 1 }`.
2. If it raises, wait 200 ms × 2 (exp backoff = 200 + 400 = 600 ms total worst case), retry once.
3. If the retry also fails → return `{ status: "error", error: str(exc), latency_ms, attempts: 2 }`.

Never raises. The planner sees the full picture in the next step's
observations.

### State changes

```python
# orchestrator/state.py
class AgentState(TypedDict):
    # ... existing fields ...

    # NEW — explicit ReAct trace
    plan_steps: list[dict]
    # [
    #   {
    #     "step": int,                # 1-based
    #     "thought": str,
    #     "actions": [{"tool": str, "params": dict}, ...],
    #     "observations": [
    #       {"status": "ok"|"error", "result"?: any, "error"?: str,
    #        "latency_ms": int, "attempts": int},
    #       ...
    #     ],
    #     "started_at": str,          # ISO-8601
    #     "duration_ms": int,
    #   },
    #   ...
    # ]
    planner_run_id: Optional[str]   # FK back to planner_runs row
```

The existing `tool_calls` and `tool_results` fields are kept and
auto-populated from the flattened action / observation lists, so
downstream nodes (`esl_gateway`, `response_formatter`, citation
extraction in `routes/chat.py`) keep working without change. We
remove them in a follow-up sprint once Sprint J/K consume
`plan_steps` directly.

### Database schema

**New table — `planner_runs`** (`backend/migrations/017_planner_runs.sql`):

```sql
CREATE TABLE public.planner_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    conversation_id UUID,
    conversation_turn_id UUID,
    intent TEXT,
    total_steps INTEGER NOT NULL DEFAULT 0,
    total_actions INTEGER NOT NULL DEFAULT 0,
    total_duration_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'cap_hit', 'error', 'vetoed')),
    plan_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX idx_planner_runs_user_conv_created
    ON public.planner_runs (user_id, conversation_id, created_at DESC);
CREATE INDEX idx_planner_runs_turn
    ON public.planner_runs (conversation_turn_id)
    WHERE conversation_turn_id IS NOT NULL;
```

**Cross-reference column on `tool_call_events`**
(`backend/migrations/018_tool_call_events_planner_run.sql`):

```sql
ALTER TABLE public.tool_call_events
    ADD COLUMN IF NOT EXISTS planner_run_id UUID,
    ADD COLUMN IF NOT EXISTS step_index INTEGER,
    ADD COLUMN IF NOT EXISTS action_index INTEGER;

CREATE INDEX IF NOT EXISTS idx_tool_call_events_planner_run
    ON public.tool_call_events (planner_run_id)
    WHERE planner_run_id IS NOT NULL;
```

**No FK constraint** on `tool_call_events.planner_run_id` deliberately —
we write tool_call_events rows during execution, before the planner_run
is finalized. A best-effort tag is enough; we don't need referential
integrity to render the UI.

### Write order

1. **Run start.** `tool_planner_node` first invocation: INSERT a
   `planner_runs` row with `status='running'`, capture its UUID into
   `state["planner_run_id"]`.
2. **Each step's executor.** For every action in the step:
   - Execute (with retry).
   - INSERT a `tool_call_events` row tagged with `planner_run_id`,
     `step_index`, `action_index`.
3. **Run end.** After the last planner step (cap hit, empty actions,
   or veto), UPDATE the `planner_runs` row with `status` (one of
   `completed`/`cap_hit`/`error`/`vetoed`), totals, full `plan_steps`,
   `finished_at`.
4. **Chat persistence.** `routes/chat.py` already writes
   `conversation_turns.metadata` — we add `plan_steps` to the metadata
   blob it persists. Same write, one more key.

### Transparency UI

`frontend/components/transparency/ToolCallsTab.tsx` gets a "Plan view"
toggle (default on for new data, off for legacy):

- **On:** rows are grouped by `(planner_run_id, step_index)`. Each
  group has a header showing the step number, the thought (clamped to
  3 lines with "show more"), and a summary like "2 actions · 412 ms".
  Action rows inside the group keep their existing detail dialog.
- **Off:** flat list as today. Legacy rows without `planner_run_id`
  always render this way.

The existing retrieval-trace section (Sprint G) keeps working
unchanged — it's per-action and lives inside the action detail
dialog.

---

## Components

| Unit | Purpose | Inputs | Outputs |
|---|---|---|---|
| `tool_planner_node` | Emit `{thought, actions}` per step; manage `planner_run_id` lifecycle | `AgentState` | Appends to `plan_steps`, updates `planner_runs` row |
| `tool_execution_node` | Run `step.actions` in parallel with per-action retry | Latest plan step | Step's `observations` filled in; `tool_call_events` rows inserted |
| `_execute_with_retry` (helper) | Wrap one tool invocation: call → retry once on exception → return structured result | One action dict | One observation dict |
| `services/planner_runs.py` (new) | DB writes: `create()`, `mark_completed()`, `mark_error()`. Best-effort; failure logs but doesn't break the turn | Run params | UUID, no exceptions |
| `routes/chat.py` (modified) | Add `plan_steps` to `conversation_turns.metadata` write | Final `state["plan_steps"]` | Existing JSONB column gets one more key |
| `transparency.ToolCallsTab` | Render grouped/flat views | Existing event list + new `planner_run_id` + `step_index` | Visual grouping when in Plan view |

---

## Data flow

```
User message
   │
   ▼
context_builder → intent_classifier ──► (research_quick → deep_research)
   │                                        │
   ▼                                        ▼
tool_planner_node (step 1)               esl_gateway → response_formatter → END
   │   creates planner_runs row (status='running')
   │   LLM emits {thought, actions}
   ▼
tool_execution_node (step 1)
   │   asyncio.gather(actions) with retry
   │   writes tool_call_events × N (tagged with planner_run_id, step_index=1)
   │   step["observations"] populated
   ▼
tool_planner_node (step 2)
   │   LLM sees prior thought + actions + observations
   │   emits {thought, actions} OR {thought, actions: []}
   ▼
   ├── actions empty? → exit loop
   └── actions present? → executor again (step_index=2)
   │
   ▼ (loop ends: empty actions, cap_hit at MAX_PLANNER_STEPS, or veto)
   │
   updates planner_runs row (status, totals, plan_steps)
   │
   ▼
esl_gateway → response_formatter
   │
   routes/chat.py writes conversation_turns.metadata.plan_steps
```

---

## Error handling

| Failure | Behavior |
|---|---|
| Single action raises | `_execute_with_retry` retries once with 200 ms backoff. Final failure becomes a `{status: "error", error: str}` observation. Step continues. |
| All actions in a step fail | Step's observations are all errors. Planner sees this in step N+1 and decides to retry, route around, or give up. |
| LLM emits malformed JSON | Fallback parser tries legacy single-tool shape. If that also fails: empty actions list with thought = "(planner emitted unparseable output, stopping)". Loop exits cleanly; turn proceeds to ESL with what we have. |
| `planner_runs` INSERT fails | Log warning, set `planner_run_id = None`. Tool calls still execute, just untagged. UI falls back to flat view. |
| `planner_runs` final UPDATE fails | Row stays as `status='running'`. A retention/janitor task (out of scope this sprint) can sweep stale rows. |
| Cap hit (`MAX_PLANNER_STEPS` reached) | Force the next planner call to set `actions: []`. Status logged as `cap_hit` (distinct from `completed`). |

---

## Testing

### Unit

- `_execute_with_retry`: succeeds first try, succeeds on retry, fails both tries, never raises. Verified latency and attempts count.
- Planner output parser: strict structured shape, legacy single-tool fallback, malformed JSON → empty actions.
- `services/planner_runs.create/mark_*`: row written with correct status; failure paths log and return None.

### Integration

- One-step plan (empty actions immediately) — round-trips through chat route, persists empty `plan_steps`, no tool_call_events rows.
- Multi-action single-step — three independent tools fire in parallel, all succeed, all three rows in `tool_call_events` share the same `planner_run_id` and `step_index=1` with distinct `action_index`.
- Multi-step plan — step 1 has 2 actions, step 2 has 1, step 3 empty (exit). Verify step indices, observation propagation, and that the LLM sees prior observations on subsequent calls.
- Partial failure — step has 3 actions, one raises both attempts. Other two succeed. Planner sees mixed observations and can continue.
- Cap hit — `MAX_PLANNER_STEPS=2`, planner never emits empty actions. Loop terminates at step 2, `status='cap_hit'`.
- Backward compatibility — planner LLM emits legacy single-tool JSON. Fallback parser converts to single-action step. Run completes normally.

### End-to-end smoke

- The existing M-KOPA Gmail integration test (Sprint F Task 2) must still pass. It currently exercises a single-tool path; we don't lose that.
- Add one new e2e test: a question that natively benefits from two parallel tools (e.g. "what was on my calendar the week of the M-KOPA email?") and assert (a) both tools are called in step 1 with `action_index` 0 and 1, (b) latency is materially less than the sum of individual tool latencies (verifies actual parallelism).

---

## Backward compatibility

- **State.** New fields are additive. Existing `tool_calls` / `tool_results` are kept and populated from the flattened actions/observations.
- **DB.** Both migrations are pure additive (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`). No data backfill needed. Existing `tool_call_events` rows have `planner_run_id IS NULL` and render in the flat Transparency view.
- **Frontend.** ToolCallsTab defaults to Plan view for events with `planner_run_id`, flat view otherwise. Existing event-detail dialogs unchanged.
- **Auto-run migrations on boot (Sprint G)** picks up the two new migration files automatically. No manual step.

---

## Rollout

1. Land all backend changes behind an env-var feature flag
   `PLANNER_PARALLEL_ENABLED` (default false). When false: planner
   prompt is unchanged, executor takes the first action only,
   `planner_runs` row still written but with a single-action step. This
   gives us a quick kill-switch if anything regresses in production.
2. Land the migrations (idempotent on boot).
3. Set the flag to true in the dev/staging env. Smoke test for two days.
4. Flip the flag in prod. Remove the flag in a follow-up after one
   stable week.

(Sprint G's "auto-run migrations on boot" makes step 2 a non-event.)

---

## Open questions

- Do we want a metric for "what fraction of steps emit >1 action"?
  If most steps stay at 1, the parallel work is overhead without
  payoff. **Resolution:** instrument it; revisit after one week of
  data. The number lives naturally in `planner_runs.total_actions /
  total_steps`.
- Should the planner LLM be allowed to call the same tool twice in one
  step with different params (e.g. two `search_documents` queries in
  parallel)? **Resolution:** yes by default — the executor doesn't
  care. The prompt nudges toward de-duplication; nothing enforces it.
- Should we cap parallelism (max concurrent actions per step)?
  **Resolution:** soft cap of 4 actions per step at the prompt level
  ("don't fan out more than 4 ways"). No hard cap in code yet; revisit
  if we see runaway plans.

---

## Verification checklist (for the implementation sprint)

```bash
cd backend
pytest tests/test_tool_planner_loop.py tests/test_tool_executor.py tests/test_planner_runs.py -v
pytest --tb=short -q             # full suite must pass

cd ../frontend
npx tsc --noEmit
```

**Manual checks:**
1. Ask "what was on my calendar the week of the M-KOPA email?" → response cites both calendar and document. Transparency Plan view shows step 1 with two actions, step 2 with the synthesis (empty actions).
2. Stop the web_search MCP, then ask a question that would call it. Plan shows the web_search action with status="error" after retry, and the next step routes to search_documents instead.
3. Set `MAX_PLANNER_STEPS=1`, ask a multi-step question. `planner_runs.status` = `cap_hit`. Response is still produced from whatever step 1 returned.
4. Toggle Transparency Plan view off → grouped view collapses to flat. Toggle back on → groups return.
