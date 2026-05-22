# Sprint J — Streaming Reasoning + Interrupts

**Date:** 2026-05-20
**Status:** Design
**Predecessors:** Sprint I ✅ (explicit ReAct + plan_steps trace)
**Successors planned:** Sprint K (episodic tool memory)

---

## Why this sprint exists

Sprint I made the planner's per-step thinking explicit and persisted —
`plan_steps[].thought` and `plan_steps[].actions` are now first-class
data on every turn. But none of that thinking reaches the user during
the turn. The chat UI still shows "Thinking…" then tokens. The agent
might be checking the calendar, searching documents, replanning around
a failed tool — the user sees a blank black box for several seconds.

Two related problems:

1. **The reasoning is opaque.** Users have no signal that the right
   work is happening. When the agent does something unexpected (or
   takes a long time), they can't tell whether to trust it. The
   transparency tab shows the trace *after* the turn — too late to
   build day-to-day trust.

2. **Some actions deserve a human gate.** Marketplace tools already
   pause via `pending_tool_confirmation`, but that's a parallel
   mechanism specific to ESL-gated writes. For non-marketplace tools
   like `query_calendar` or `web_search`, users with strong privacy
   preferences ("ask me before you read my calendar") have no
   recourse. Sprint H added values declarations; this sprint gives
   those values teeth at the tool boundary.

Sprint J makes the agent's thinking visible as it happens and lets the
user gate any tool they choose. It's the visibility-and-control layer
that Sprint I made structurally possible.

---

## Goals

1. **Stream the planner's thought as it's generated** (token-level)
   into a new SSE channel separate from the response.
2. **Emit a structured `plan_step_actions` event** when the planner
   has committed to the step's actions, plus `action_start` /
   `action_complete` per action.
3. **Pause the graph mid-turn for user-flagged actions** via LangGraph's
   `interrupt()`. The user sees the planned action with Approve /
   Skip / Cancel / Trust-from-now-on, and the resume continues from
   the checkpoint.
4. **Layered safety controls** — three levels of confirmation
   preferences the user can stack:
   - **Master toggle** (`users.safe_mode_enabled`): when true, every
     action pauses.
   - **Category toggles** (`user_category_preferences`): tools belong
     to one of four categories (`read-personal`, `read-external`,
     `write-personal`, `write-external`); user toggles per category.
   - **Per-tool list** (`user_tool_preferences`): finest grain;
     overrides categories only if it ADDS a pause (resolution is
     "pause if any layer says so").
   All three default to off — Sprint J adds no friction unless the
   user opts in.
5. **Durable pauses.** A pause that takes the user 10 minutes to
   resolve must survive a backend restart. LangGraph's PostgresSaver
   checkpointer; 24h TTL prune via the existing retention job.

---

## Non-goals

- **Edit-the-params on pause.** Approving means "run with these
  params." If the user wants different params, they Skip and rephrase.
  (Out of scope; revisit if user feedback demands it.)
- **Risk-level tagging on tools as a system-level default.** We
  considered a `risk_level='high'` metadata flag that would auto-trigger
  pauses; rejected in favor of per-user opt-in. (The project's "user
  control non-negotiable" principle outranks "smart defaults that take
  agency away." Tool *categories* are different — they're a routing
  hint, not an automatic policy.)
- **LLM-flagged risky actions.** Non-deterministic judge; bad fit for
  a project framed around trust.
- **Natural-language safety rules** (e.g. "never email anyone before
  checking with me"). Worth doing, but it's an ESL-engine extension,
  not a Sprint-J UI feature. Deferred to a future sprint that extends
  the ESL evaluator.
- **Replacing the marketplace `pending_tool_confirmation` path.**
  That mechanism remains. It serves a different need (ESL gate over
  third-party tool actions). Sprint J's interrupts and marketplace
  pending coexist.
- **Multi-action approval.** Interrupt fires per-action, not
  per-step. A step with 3 user-flagged actions pauses 3 times. Not
  beautiful but predictable — auto-batching approvals invites mistakes.

---

## Architecture

### Streaming reasoning

The existing `stream_langgraph` function uses
`graph.astream_events(version="v2")` and routes specific event kinds
into SSE payloads. Sprint I added structured `plan_steps` to state
but didn't stream them. Sprint J adds three new SSE event types
emitted from the same astream_events loop:

| Event | When | Payload |
|---|---|---|
| `thought_token` | LLM token stream while `tool_planner` node is running | `{ token: str, step: int }` |
| `plan_step_actions` | `on_chain_end` for `tool_planner` after a step is committed | `{ step: int, actions: [{tool: str, params: dict}] }` |
| `action_start` | Per action in `tool_execution_node` | `{ step: int, action_index: int, tool: str }` |
| `action_complete` | Per action after `_execute_with_retry` returns | `{ step: int, action_index: int, tool: str, status: 'ok'\|'error', latency_ms: int }` |

The existing `token` event (response tokens) is unchanged. Channel
separation: planner-node tokens become `thought_token`; synthesis
(executor's final synthesis call) and response_formatter tokens stay
on `token`. The chat page wraps `thought_token` events into a
collapsible "Reasoning" panel above the response.

Existing tool events (`tool_use`, `tool_result`, `tool_pending_
confirmation`) keep firing — Sprint J's new events are additive. The
frontend can choose to migrate to the new richer events over time.

### Interrupt mechanism

**Where it fires:** inside `tool_execution_node`, before each action.

**Resolution order (pause if ANY layer says so):**

```python
def _should_confirm(user_id: str, tool: ToolMetadata) -> bool:
    # Layer 1: master toggle. If on, pause everything.
    if users.safe_mode_enabled[user_id]:
        return True
    # Layer 2: category toggle.
    if tool.category in user_category_preferences[user_id]:
        return True
    # Layer 3: per-tool list.
    if tool.name in user_tool_preferences[user_id]:
        return True
    return False
```

The three layers are independent rows/columns; the executor reads
them with one query (joined on user_id) at the start of the step
and caches the result for the step's lifetime. No layer "overrides"
another — they accumulate. Approving with "Trust this tool from now
on" removes only the matching row at the per-tool layer (so master
or category still apply if set).

For each `action` in the step:

```python
should_confirm = (
    safe_mode_on
    or action["category"] in confirmed_categories
    or action["tool"] in confirmed_tools
)
if should_confirm:
    # LangGraph interrupt — pauses the graph, persists state via
    # the configured checkpointer, returns to stream_langgraph.
    decision = interrupt({
        "kind": "user_confirmation",
        "step": step_index,
        "action_index": ai,
        "tool": action["tool"],
        "category": action["category"],
        "params": action["params"],
        "reason": _explain_reason(safe_mode_on, action),  # "safe mode is on" or "write-external category" or "tool query_calendar"
    })
    # On resume, `decision` is the value passed to Command(resume=...)
    if decision["action"] == "cancel":
        # Mark plan_step observation as cancelled, set planner_runs
        # status to 'cancelled', break out of the executor loop.
        ...
    elif decision["action"] == "skip":
        # Append a 'skipped' observation, continue to next action.
        ...
    elif decision["action"] == "trust":
        # Delete the row from user_tool_preferences, then fall through
        # to the normal execution path.
        _delete_tool_preference(user_id, action["tool"])
    # else: 'approve' — fall through to normal execution
```

`interrupt()` raises a special exception that LangGraph catches,
persists the entire `AgentState` plus the pending node-resume info to
the checkpointer, and exits the graph cleanly. Control returns to
`stream_langgraph`.

### Checkpointer wiring

```python
# orchestrator/graph.py
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

_checkpointer = None

async def get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
        await _checkpointer.setup()  # idempotent table creation
    return _checkpointer

async def build_graph_async():
    cp = await get_checkpointer()
    g = StateGraph(AgentState)
    # ... add nodes / edges as before ...
    return g.compile(checkpointer=cp)
```

The checkpointer creates three tables on `setup()`:
`checkpoints`, `checkpoint_writes`, `checkpoint_migrations`. We don't
manage these directly — LangGraph owns the schema.

**Thread identity.** Each turn is one thread. We use the assistant
turn's UUID:

```python
thread_id = conversation_turn_id  # str(uuid)
config = {"configurable": {"thread_id": thread_id}}
async for event in graph.astream_events(initial_state, config, version="v2"):
    ...
```

On resume:

```python
config = {"configurable": {"thread_id": existing_thread_id}}
async for event in graph.astream_events(Command(resume=decision), config, version="v2"):
    ...
```

### Pause SSE event + resume route

When the graph emits an `interrupt`, `stream_langgraph` catches it
via the `__interrupt__` chain event (or by inspecting the final state
for an `__interrupt__` field after astream_events drains). It emits:

```json
{
  "event": "plan_paused",
  "thread_id": "01HXXXX-...",
  "step": 1,
  "action_index": 1,
  "tool": "query_calendar",
  "category": "read-personal",
  "params": { "days_back": 30 },
  "reason": "category 'read-personal' is set to ask before running"
}
```

The `reason` string is human-readable; the frontend renders it under
the action chip so the user understands *why* the pause happened
(useful when they have multiple layers configured and want to know
which one triggered).

Then closes the SSE stream cleanly. The frontend renders Approve /
Skip / Cancel / "Trust this tool from now on" under the paused action
chip.

User clicks → frontend POSTs to a new route:

```
POST /api/chat/resume
{
  "thread_id": "01HXXXX-...",
  "decision": "approve" | "skip" | "cancel",
  "trust": false   // if true on approve, also drop from preferences
}
```

The route validates the thread belongs to `user_id`, then opens a new
SSE stream that re-enters the graph via
`Command(resume={action: "approve", ...})`. The stream emits the
remaining `action_complete`, possibly more `plan_step_actions`, then
`done`.

### Safety preferences storage

Three storage targets, one per layer.

**Migration `019_user_safe_mode.sql`** — the master toggle:

```sql
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS safe_mode_enabled BOOLEAN NOT NULL DEFAULT FALSE;
```

**Migration `020_user_category_preferences.sql`** — the category layer:

```sql
CREATE TABLE IF NOT EXISTS public.user_category_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (category IN (
        'read-personal', 'read-external', 'write-personal', 'write-external'
    )),
    requires_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, category)
);

CREATE INDEX idx_user_category_preferences_user
    ON public.user_category_preferences (user_id);
```

**Migration `021_user_tool_preferences.sql`** — the per-tool layer:

```sql
CREATE TABLE IF NOT EXISTS public.user_tool_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    requires_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, tool_name)
);

CREATE INDEX idx_user_tool_preferences_user
    ON public.user_tool_preferences (user_id);
```

All three default to off (`safe_mode_enabled=false`, no rows in
either preferences table). Sprint J adds zero friction until the
user opts in.

### Tool category metadata

Every tool declares a `category` in its metadata. This lives next to
the existing `tool_id` / `action_name` / `risk_level` keys used by
the marketplace path:

| Tool | Category |
|---|---|
| `query_memory` | `read-personal` |
| `query_calendar` | `read-personal` |
| `get_user_goals` | `read-personal` |
| `search_documents` | `read-personal` |
| `web_search` | `read-external` |
| `create_note` | `write-personal` |
| Marketplace tools (Gmail send, Slack send, Calendar write…) | `write-external` |

The category lives in `services/langchain_tools.py` where each tool
class is defined — one line per class. Unknown categories fall back
to `write-external` (most conservative). The category is also
included on every `plan_step_actions` SSE event and `tool_call_events`
row so Transparency can color-code or filter by it later.

### Backend API

| Endpoint | Method | Purpose |
|---|---|---|
| `GET  /api/settings/safety` | GET | Return the full safety preferences shape: `{ safe_mode_enabled, categories: {...}, tools: {...}, available_tools: [{name, category}, ...] }`. One request hydrates the entire settings page. |
| `PUT  /api/settings/safety/safe-mode` | PUT | Body `{ enabled: bool }`. Toggles the master switch. |
| `PUT  /api/settings/safety/categories/{category}` | PUT | Body `{ requires_confirmation: bool }`. Upserts the category row. `requires_confirmation=false` deletes the row. |
| `PUT  /api/settings/safety/tools/{tool_name}` | PUT | Body `{ requires_confirmation: bool }`. Upserts the per-tool row. `requires_confirmation=false` deletes the row. |
| `POST /api/chat/resume` | POST | Resume a paused graph thread with the user's decision. |

### Frontend changes

1. **`/dashboard/settings/safety` (new page).** Three sections:
   - **Top: master toggle.** A single Switch labeled "Ask me before any
     action runs." Bound to `safe_mode_enabled`. When ON, the rest of
     the page goes muted/disabled — the master overrides everything.
   - **Middle: category grid.** 2×2 layout of toggles:
     - Read · Personal (your calendar, memory, goals, documents)
     - Read · External (web search)
     - Write · Personal (notes you save)
     - Write · External (emails, Slack messages, calendar writes)
     Each toggle hits `PUT /api/settings/safety/categories/{category}`.
   - **Bottom: per-tool list.** Existing list (per the original spec)
     of every registered tool with an individual toggle. Each row also
     shows the tool's category as a small tag so the user can see why
     a category toggle would affect it. Toggle hits
     `PUT /api/settings/safety/tools/{tool_name}`.

   All three sections read from one initial `GET /api/settings/safety`.
2. **Chat page** (`/dashboard/chat`):
   - New `<ReasoningPanel>` component that listens for `thought_token`,
     `plan_step_actions`, `action_start`, `action_complete` events
     and renders them above the assistant message. Collapsible
     (default: open while streaming, collapses to a one-liner when
     the turn ends).
   - On `plan_paused` event: render a confirmation prompt with the
     four buttons. Hide the input box (no new messages can be sent
     until the user decides). The prompt sticks around until the
     user clicks; backend stream is closed, so reconnecting is the
     user's button click triggering `POST /api/chat/resume`, which
     opens a fresh SSE stream that streams the rest of the turn.
3. **`/dashboard/transparency`:** the Tool Calls tab already groups
   by `(planner_run_id, step_index)` (Sprint I Task 14). Sprint J
   doesn't change this — it just adds richer data for events of the
   same conversation turn.

### Retention

Add to the existing daily retention prune (Sprint E `services/retention.py`):

```python
# Prune LangGraph checkpoints older than 24h. Pauses we haven't
# resumed within that window are abandoned — the user can always
# start a fresh turn.
await db.execute("DELETE FROM checkpoints WHERE thread_ts < NOW() - INTERVAL '24 hours'")
await db.execute("DELETE FROM checkpoint_writes WHERE thread_ts < NOW() - INTERVAL '24 hours'")
```

---

## Data flow (with interrupt)

```
User: "summarize my next meeting and email the attendees"
   │
   ▼
context_builder → intent_classifier → tool_planner
   │   LLM streams thought: "Let me check the calendar..."
   │   → emits thought_token events to client
   │   → commits actions = [query_calendar(...)]
   │   → emits plan_step_actions event
   ▼
tool_execution_node
   │   For action[0] = query_calendar:
   │     - look up user_tool_preferences
   │     - user has "always ask before query_calendar" toggled on
   │     - emits action_start event
   │     - calls interrupt({tool: query_calendar, params: {...}})
   │     ↓ graph pauses, state persisted to checkpoints table
   ▼
stream_langgraph catches interrupt
   │   - emits plan_paused event
   │   - closes SSE stream
   │
   [...user reads, clicks Approve...]
   │
   ▼
Frontend POST /api/chat/resume {thread_id, decision: "approve"}
   │
   ▼
routes/chat.py opens new SSE stream
   │   graph.astream_events(Command(resume={action: "approve"}), config={thread_id})
   ▼
tool_execution_node resumes inside the interrupt branch
   │   decision["action"] == "approve" → fall through
   │   → _execute_with_retry runs query_calendar
   │   → emits action_complete event
   │   → continues to next action / planner step / synthesis
   ▼
esl_gateway → response_formatter → done
   │   tokens stream on the normal `token` channel
   ▼
END
```

---

## State changes

No new `AgentState` fields are required. LangGraph's checkpointer
persists the full state across the pause; the `interrupt()` call's
payload is what reaches the frontend via the `plan_paused` event, and
the frontend echoes it back unchanged on resume. Thread identity is
managed via the config dict, not state.

---

## File map

| Path | Action |
|---|---|
| `backend/migrations/019_user_safe_mode.sql` | CREATE — adds `users.safe_mode_enabled` column |
| `backend/migrations/020_user_category_preferences.sql` | CREATE |
| `backend/migrations/021_user_tool_preferences.sql` | CREATE |
| `backend/services/safety_preferences.py` | CREATE — unified service for the three layers (load_for_user returns the combined shape used by the executor; per-layer CRUD methods used by the routes) |
| `backend/routes/safety_preferences.py` | CREATE — REST endpoints for /api/settings/safety/* |
| `backend/services/langchain_tools.py` | MODIFY — declare `category` on each tool's metadata |
| `backend/orchestrator/graph.py` | MODIFY — add PostgresSaver, build_graph_async, thread-aware stream_langgraph; handle resume path |
| `backend/orchestrator/nodes/tools.py` | MODIFY — `tool_execution_node` checks layered preferences, calls `interrupt()` when any layer requires confirmation |
| `backend/routes/chat.py` | MODIFY — new `POST /api/chat/resume` endpoint |
| `backend/services/retention.py` | MODIFY — prune `checkpoints` + `checkpoint_writes` > 24h |
| `backend/main.py` | MODIFY — register safety_preferences router |
| `backend/tests/test_safety_preferences_service.py` | CREATE — covers all three layers + the resolution-order logic |
| `backend/tests/test_safety_preferences_route.py` | CREATE |
| `backend/tests/test_interrupt_flow.py` | CREATE — integration test for interrupt + resume (tests every layer triggers a pause; tests the Trust action removes only the per-tool row) |
| `frontend/app/dashboard/settings/safety/page.tsx` | CREATE — three-section settings UI |
| `frontend/components/chat/ReasoningPanel.tsx` | CREATE — streamed thought + action chips |
| `frontend/components/chat/PausedActionPrompt.tsx` | CREATE — Approve/Skip/Cancel/Trust UI; shows the `reason` string |
| `frontend/app/dashboard/chat/page.tsx` | MODIFY — wire ReasoningPanel + handle plan_paused event |
| `frontend/lib/api.ts` | MODIFY — `safetyApi` namespace + resume endpoint |

~19 files (12 new, 7 modified). Slightly bigger than the original
single-layer scope, but the layers all share the same execution
plumbing — the additional cost is mostly UI surface and three
extra migration files (which auto-apply on boot anyway).

---

## Error handling

| Failure | Behavior |
|---|---|
| Checkpointer DB write fails on pause | Log warning. Graph still pauses but the resume window is shorter (in-memory state may be lost on restart). Acceptable degradation. |
| User submits resume for a thread that doesn't exist (expired or wrong user) | 404 with a clear "this conversation has expired — please start a fresh turn" message. |
| User submits resume for a thread that's already resumed | Idempotency: the LangGraph `Command(resume=...)` on an already-resumed thread is a no-op. Surface as "already resumed; please reload" 409. |
| Resume payload missing `decision` | 422 with the validation error. |
| User toggles a tool preference but their CURRENT in-flight turn was already past that action | No effect on the current turn (preferences are loaded per-action at execute time, but if we're past it, we're past it). Affects the next turn. |
| Interrupt body too large for checkpoint table column | Truncate the params field at 4KB and log. Resume still works; the user sees a truncated preview. |
| Thread is checkpointed but `tool_execution_node` code has been deployed with incompatible state shape | Treat resume as fresh turn: emit a `stale_resume` event, the frontend prompts the user to retry. |

---

## Testing

### Unit

- `services/tool_preferences.py`: list / put / delete; per-user isolation; idempotent put.
- `routes/tool_preferences.py`: auth required; 404 on unknown tool name.
- `routes/chat.py::resume`: 404 / 409 / 422 paths; happy-path enters astream_events on the right thread_id.

### Integration

- **Streaming events.** Drive a turn end-to-end (mocked LLM emits a thought + one tool call); assert SSE event sequence includes `thought_token` then `plan_step_actions` then `action_start` then `action_complete` then `token` (response) then `done`.
- **Interrupt + approve.** User has `query_calendar` in preferences with `requires_confirmation=true`. Turn 1: graph pauses, `plan_paused` event emitted, stream closes. POST /api/chat/resume with approve. New stream completes the turn. Assert the calendar tool DID execute (real `_execute_with_retry` call happened).
- **Interrupt + skip.** Same setup, decision=skip. Assert the action observation is `{status: 'skipped', reason: 'user'}` and the planner sees it in the next step.
- **Interrupt + cancel.** Decision=cancel. Assert `planner_runs.status = 'cancelled'`, no further actions execute, `done` event still fires.
- **Interrupt + trust.** Decision=approve with `trust=true`. After resume, assert the row was deleted from `user_tool_preferences`. A second turn that calls the same tool does NOT pause — *as long as the master toggle is off and the category layer doesn't catch it*. If a higher layer is still on, "Trust this tool" does NOT magically silence it (we don't want one click to disable a category the user explicitly enabled).
- **Layered resolution.** User has `safe_mode_enabled=true` AND a category toggle AND a per-tool toggle, all set to require confirmation. Assert one (and only one) pause fires per action; assert `reason` reflects the highest-priority layer (master > category > per-tool).
- **Trust action with master on.** Master is on, user clicks Approve+Trust. Per-tool row deleted; next call still pauses (master still wins). UI should hint this — the PausedActionPrompt's Trust button is disabled (or marked "won't help — safe mode is on") when master is on.
- **Resume on a turn whose checkpointed code differs.** Force a state shape mismatch; assert the route returns a usable error.

### End-to-end smoke

- Real backend with Postgres checkpointer wired up. Set `query_calendar` to require confirmation. Send a chat message that triggers a calendar lookup. Watch the SSE stream pause; click Approve in the UI; watch the turn complete. Restart the backend mid-pause and confirm the resume still works (durability).

---

## Backward compatibility

- All new SSE events are additive. Existing frontend code that listens for `token`, `tool_use`, `tool_result`, `tool_pending_confirmation`, `done` keeps working unchanged.
- The graph is now compiled with a checkpointer, but turns that don't pause behave identically to today (checkpointer writes are background; no observable behavior change for non-interrupt turns).
- `user_tool_preferences` defaults to empty — no user is opted into any interrupts. Sprint J behavior is invisible until a user toggles something.
- Marketplace `pending_tool_confirmation` path is unchanged. The two pause mechanisms coexist.

---

## Rollout

1. Land all backend + frontend changes behind a feature flag `STREAMING_REASONING_ENABLED` (default false). When false: the planner runs unchanged, no `thought_token` / `plan_step_actions` / `action_start` / `action_complete` events emitted, checkpointer still wired (no-op for non-interrupt turns), `user_tool_preferences` table populated but never queried.
2. Land migrations.
3. Flip flag to true in staging. Smoke test the interrupt path. Smoke test a restart mid-pause.
4. Flip in prod. Watch for any latency regression in non-interrupt turns (none expected, but the checkpointer writes add ~10 ms per node transition).
5. Remove the flag after one stable week.

---

## Open questions

- **Should the ReasoningPanel persist after the turn ends, or auto-collapse?** Start with auto-collapse to a one-line summary ("3 steps · 5 actions · 1.2s"). User can click to expand. Don't litter the chat history with verbose traces by default. Configurable in settings (Sprint J+ if anyone asks).
- **What about the `/ask` slash command that forces a `search_documents` call?** It still works — the forced action goes through the same execution path, including the user_tool_preferences check. If a user has `search_documents` on their ask list, /ask will pause.
- **Cap on consecutive pauses?** A pathological plan that has 5 user-flagged actions in 5 steps would pause 5 times. Acceptable for v1; if friction is real, we add a "Approve all remaining" button in a follow-up.

---

## Verification checklist (for the implementation sprint)

```bash
cd backend
pytest tests/test_tool_preferences_service.py tests/test_tool_preferences_route.py tests/test_interrupt_flow.py -v
pytest --tb=short -q

cd ../frontend
npx tsc --noEmit
```

**Manual checks:**
1. Visit `/dashboard/settings/tools` → toggle "always ask" on for `query_calendar`. Save.
2. Send a chat message that would trigger a calendar lookup. The Reasoning panel appears with the thought streaming token-by-token. Then "calendar lookup pending approval" with four buttons.
3. Click Approve → action completes, calendar data appears in response.
4. New turn with the same trigger → pauses again.
5. Approve with "Trust this tool from now on" → action runs.
6. New turn with the same trigger → no pause this time.
7. Restart backend mid-pause (kill -9 the process) → restart → check that the paused thread still resumes correctly.
