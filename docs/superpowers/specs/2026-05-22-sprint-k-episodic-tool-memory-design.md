# Sprint K — Episodic Tool Memory

**Date:** 2026-05-22
**Status:** Design
**Predecessors:** Sprint I (planner_runs trace) ✅, Sprint J (streaming reasoning + interrupts) ✅ (PR #74)
**Successors planned:** none yet — Sprint K closes the I → J → K agent-integration deepening track.

---

## Why this sprint exists

Sprint I made every plan a first-class persisted artifact (`planner_runs`
rows). Sprint J streamed those plans to the user and added per-tool
safety gates. But the agent itself doesn't yet learn anything from its
own history — every turn replans from scratch, even when the user has
already asked something very similar before.

Two consequences:

1. **Repetitive planning latency.** The user asks "what was on my
   calendar this week" on Monday; the planner picks `query_calendar`.
   The same user asks the same question on Tuesday; the planner picks
   `query_calendar` again from a blank slate. The LLM is doing the same
   reasoning N times.

2. **No felt sense of "the agent remembers me."** The whole point of a
   personal assistant is that it accumulates a model of how its user
   thinks. Without episodic memory the agent feels stateless even when
   the data tier is rich.

Sprint K adds **soft prompt augmentation from past completed plans**:
at the start of every planner step, we fetch the K most similar past
runs for this user, format them into a short SystemMessage, and prepend
it to the planner's input. The LLM retains full agency — it can use,
adapt, or ignore the precedent.

---

## Goals

1. **Persist per-turn message embeddings.** After every completed turn
   with at least one successful tool action, write the user's message +
   plan summary to a new Weaviate collection.
2. **Recall at planner-step start.** Embed the current message, do a
   hybrid search (alpha=0.7) over the user's own `PlannerRunMemory`,
   filter by recency, return top-3 above a similarity threshold.
3. **Prompt augmentation.** Format the matches as a brief SystemMessage
   and prepend it to the planner's input. Empty matches → no message
   injected.
4. **Transparency surface.** When memory was consulted on a turn, fold
   a `memory_used` array into the first tool_planner step's
   `tool_call_events.output`. Transparency tab renders it as a "Drew on
   past plans" section in the detail dialog. Chat UI stays clean.
5. **No write/read latency penalty on the visible path.** The Weaviate
   write is fire-and-forget via `asyncio.create_task`. The read happens
   inline at planner-step start but is gated and time-bounded.

---

## Non-goals

- **Pruning old memory.** The 90-day recency filter in the read path
  silently ignores stale rows; nothing physically deletes them yet. If
  the collection bloats, add a sweep to the existing daily retention
  job in a follow-up.
- **Editing or forgetting specific memories from the UI.** Users can
  delete their account or the underlying conversation (which cascades
  to `planner_runs`); they can't yet say "forget that I asked about
  X". Worth doing later as part of an ESL "right to be forgotten"
  feature; out of scope here.
- **Cross-user memory.** `user_id` is in every WHERE clause on every
  read and every write. Cross-user transfer is impossible by
  construction.
- **Confidence-weighted planning.** We don't tell the planner "use
  this past plan with 80% confidence." The recall is a hint in
  natural language; the LLM decides what to do with it.
- **Memory that changes ESL behavior.** The Ethical Safeguard Layer
  is still the gateway for every user-facing action. Sprint K only
  influences planning, not the gate.
- **Re-running an old plan verbatim.** No "soft routing" pre-planner
  node (rejected during brainstorming). Every turn still goes through
  the planner.

---

## Architecture

### Read path (per planner step)

```
tool_planner_node receives state
   │
   ▼
[gated on EPISODIC_MEMORY_ENABLED]
   │
   ▼
PlannerRunMemoryService.recall(user_id, message, k=3, min_sim=0.6, max_age_days=90)
   │   1. generate_query_embedding(message, task="retrieval_query")
   │   2. hybrid_search PlannerRunMemory collection
   │      WHERE user_id = %s AND created_at > NOW() - 90d
   │      ORDER BY hybrid_score DESC LIMIT k
   │   3. filter score < 0.6
   ▼
List[PastRun] (may be empty)
   │
   ▼
Format → SystemMessage prepended to planner input
   │
   ▼
LLM emits {thought, actions: [...]}
```

### Write path (on turn completion)

```
PlannerRunsService.finalize(...)  [Sprint I, called by graph.py at end of turn]
   │
   ▼
status == "completed" AND any observation.status == "ok"?
   │ no  → return (this turn's plan isn't worth remembering)
   │ yes
   ▼
asyncio.create_task(
    PlannerRunMemoryService.write(
        user_id, run_id, message, plan_summary
    )
)
   │   1. embedding_service.generate_query_embedding(message, task="retrieval_document")
   │   2. Weaviate insert: { user_id, planner_run_id, message_text,
   │                         plan_summary, status, created_at, vector }
   │
   ▼ (background; original finalize() returns immediately)
   logs success or failure
```

The fire-and-forget pattern matches existing telemetry conventions
(`_post_stream_store`, `tool_telemetry.record_tool_call`). The created
task is intentionally not awaited — if it raises, the exception is
logged inside the task body and discarded.

### Weaviate collection schema

```python
# PlannerRunMemory class (per-user partitioned by user_id property)
{
    "class": "PlannerRunMemory",
    "vectorizer": "none",  # we provide vectors explicitly
    "properties": [
        {"name": "user_id",         "dataType": ["string"]},  # primary filter
        {"name": "planner_run_id",  "dataType": ["string"]},  # back-ref to planner_runs.id
        {"name": "message_text",    "dataType": ["text"]},    # the user's question
        {"name": "plan_summary",    "dataType": ["text"]},    # "search_documents → query_calendar"
        {"name": "status",          "dataType": ["string"]},  # always 'completed' for now; future-proof
        {"name": "created_at",      "dataType": ["date"]},    # for recency filter
    ],
}
```

Initialization happens on first use via a `ensure_collection()` helper
in `utils/weaviate_client.py` (matches the pattern for `DocumentMemory`).

### State changes

None. `AgentState` is unaffected. The recall happens inside
`tool_planner_node` and the result is consumed in the same call —
nothing needs to persist on state across nodes.

### Prompt format

```
You've handled similar questions before. Past examples (most recent first, may be stale):
- "what was the M-KOPA email about" → search_documents (completed in 1.2s, 1 step)
- "summarize this week's calendar" → query_calendar (completed in 0.4s, 1 step)

Use these as hints, not rules — the current question may need a different plan.
```

`plan_summary` is a deterministic compact string built from each run's
`plan_steps`: `" → ".join(unique tool names in order of first appearance)`,
plus `(completed in {N}s, {steps} step(s))`. Capped at a reasonable
length for prompt budget; truncation indicated by `…`.

### Telemetry / Transparency

When `recall()` returns non-empty, `tool_planner_node` includes a
`memory_used` field in the step's tool_call_events output:

```json
{
  "memory_used": [
    {
      "planner_run_id": "01HXY...",
      "message_text": "what was the M-KOPA email about",
      "plan_summary": "search_documents (completed in 1.2s, 1 step)",
      "similarity": 0.81
    },
    ...
  ]
}
```

The Transparency tab's tool-call detail dialog gets a new section
"Drew on past plans" that renders this array. Existing retrieval-trace
section (Sprint G) keeps working unchanged.

### Failure handling

| Failure | Behavior |
|---|---|
| `recall()` Weaviate query fails | Log warning, return empty list. Planner proceeds without memory; behavior identical to flag-off. |
| `recall()` embedding API fails | Same — log + empty list. |
| `write()` background task fails | Logged inside the task body; main turn unaffected. |
| Collection doesn't exist yet | `ensure_collection()` is called lazily on first `write()` or `recall()`. If creation fails, both operations no-op with a warning. |
| Cold-start user | `recall()` returns []. No SystemMessage. No change in behavior. |
| 90-day filter excludes all matches | Same as cold-start. |

### Configuration

| Setting | Default | Purpose |
|---|---|---|
| `EPISODIC_MEMORY_ENABLED` | `false` | Feature flag. When False: no writes, no recalls, no prompt changes. |
| `EPISODIC_MEMORY_TOP_K` | `3` | Max past runs returned per recall. |
| `EPISODIC_MEMORY_MIN_SIMILARITY` | `0.6` | Hybrid score floor. Below this → drop the match. |
| `EPISODIC_MEMORY_MAX_AGE_DAYS` | `90` | Recency filter on the `created_at` property. |

All four are config-driven; no recompile needed to tune in
staging/prod.

---

## File map

| Path | Action |
|---|---|
| `backend/config.py` | MODIFY — four new settings (flag + three tuning knobs) |
| `backend/.env.example` | MODIFY — document the four settings |
| `backend/utils/weaviate_client.py` | MODIFY — add `ensure_planner_run_memory_collection()` helper |
| `backend/services/planner_run_memory.py` | CREATE — `write()` + `recall()` |
| `backend/services/planner_runs.py` | MODIFY — `finalize()` schedules the memory write on success |
| `backend/orchestrator/nodes/tools.py` | MODIFY — `tool_planner_node` calls `recall()`, prepends SystemMessage, folds `memory_used` into the first step's telemetry |
| `backend/tests/test_planner_run_memory.py` | CREATE — unit tests for `recall()` filtering + `write()` happy path / failure paths |
| `backend/tests/test_planner_memory_recall.py` | CREATE — integration test for SystemMessage injection in the planner |
| `frontend/components/transparency/ToolCallsTab.tsx` | MODIFY — render "Drew on past plans" section when `output.memory_used` present |

~9 files (4 new, 5 modified).

---

## Testing

### Unit

- `PlannerRunMemoryService.recall`: returns empty on no matches; respects user_id filter; respects min_similarity threshold; respects max_age_days; honors top_k. DB/embedding failure → empty list, no raise.
- `PlannerRunMemoryService.write`: builds the right Weaviate object shape; calls embedding service with `retrieval_document` task type; write failure logs and returns. `ensure_collection()` is called lazily.
- `PlannerRunsService.finalize` (modified): only schedules a memory write when status='completed' AND any observation.status=='ok'. Schedules nothing for cap_hit/error/vetoed/cancelled or all-failed plans.

### Integration

- `tool_planner_node` with `EPISODIC_MEMORY_ENABLED=True`: when `recall()` returns 2 matches, the planner LLM is invoked with a system message containing both. When `recall()` returns [], no system message is added (the prior message list is byte-identical to flag-off).
- Telemetry: when recall returns matches, the first step's tool_call_events row has a non-empty `memory_used` JSONB field. When recall returns empty, `memory_used` is absent or empty array.

### End-to-end smoke

- Run a turn → `planner_runs` row finalized with `completed` + ok action → confirm a Weaviate row exists in `PlannerRunMemory` for that user.
- Send the same message again → confirm the planner's first step has `memory_used` populated.
- Toggle `EPISODIC_MEMORY_ENABLED=false` → confirm Weaviate writes stop and recall returns [].

---

## Rollout

1. Land all backend + frontend changes behind `EPISODIC_MEMORY_ENABLED=false`. Default behavior identical to today.
2. Flip to `true` in dev/staging. Have one developer run ~10 turns to seed memory, then send similar queries and verify recall in the Transparency tab.
3. Tune the three tuning knobs based on observed recall quality.
4. Flip in prod.
5. Remove the flag after one stable week.

---

## Open questions deferred to execution

- **Plan summary string format.** I'm proposing
  `"tool_a → tool_b (completed in Xs, Y step(s))"`. The implementer
  can refine if needed; the contract is "short, deterministic,
  human-readable."
- **Hybrid search alpha.** Sprint A's RAG uses `alpha=0.7` (favors
  dense). The same default should work for messages; if BM25 is
  noticeably more useful for short queries we can tune in a follow-up.
- **Weaviate batch writes.** Sprint K writes one object per completed
  turn — not batchable in practice. If we later add reflection or
  multi-turn writes per session, revisit.

---

## Verification checklist (for the implementation sprint)

```bash
cd backend
pytest tests/test_planner_run_memory.py tests/test_planner_memory_recall.py -v
pytest --tb=short -q

cd ../frontend
npx tsc --noEmit
```

**Manual checks** (after flipping `EPISODIC_MEMORY_ENABLED=true`):

1. Ask "what was on my calendar this week" → completes successfully → wait for the background task to finish (~1s) → `psql -c "SELECT id FROM planner_runs ORDER BY created_at DESC LIMIT 1"` returns the new run.
2. Same prompt again, new turn → in Transparency tab, click the first `tool_planner` event → "Drew on past plans" section shows the previous run's message + plan summary + similarity.
3. With `EPISODIC_MEMORY_ENABLED=false`, ask the same question → no `memory_used` field; no SystemMessage in the planner's input (verify by inspecting LangSmith / a temporary log line if needed).
4. Send an entirely unrelated question (e.g. "translate hello to French") → memory_used is empty or absent. Sanity check the similarity threshold is working.
