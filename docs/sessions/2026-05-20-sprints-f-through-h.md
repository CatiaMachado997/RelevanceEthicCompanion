# Session summary — Sprints F, G, H

**Project:** Ethic Companion (an AI assistant gated by an Ethical Safeguard Layer)
**Branch:** `claude/pensive-jemison-645b09`
**PR:** [#48](https://github.com/CatiaMachado997/RelevanceEthicCompanion/pull/48)
**Span:** three sprints, one hotfix, ~20 commits
**Final state:** backend 444 passed / 2 skipped · frontend `tsc --noEmit` clean · end-to-end RAG verified on real Gmail content

---

## What the session was for

Ethic Companion already had the four product pillars in place (RAG over user
documents, connector framework for Gmail/Slack/Calendar, an agentic
orchestrator, work management). What it didn't have was a coherent
day-one experience. The user's words at the start:

> "the app doesn't feel very easy to use, it has a lot of functionalities
> but it kinda feels off to use the integrations, like it can't use the
> whole functionalities like I planned"

> "I synced and don't know, when I ask it tries and fails, dashboard today
> no tasks due"

> "when I type hello it opens a new blank chat also annoying"

> "also these errors are annoying"

Three sprints came out of that, each scoped to fix a specific class of
"this feels broken even though it technically works":

| Sprint | What broke the trust | What we shipped |
|---|---|---|
| **F** — Daily-use polish | Sync said "done" but retrieval found nothing | Index-failure observability, reindex endpoint, status footer, Today feed, planner bias, error-noise sweep, blank-chat fix |
| **G** — Retrieval depth + ops safety | Hours lost to silent schema drift; retrieval ranking was fusion-only | Auto-run migrations on boot, PDF/DOCX ingestion, Jina rerank with graceful fallback, retrieval breadcrumbs in Transparency |
| **H** — First-run onboarding | New users land on an empty dashboard with no signal of what to do | `users.onboarded_at`, `/onboarding` wizard (connect → values → goal), redirect guard, sidebar nudge |

The thread that runs through all three: the ESL ("trust over engagement") is
the project's whole reason for existing, and an assistant that *feels* broken
on day one can't be trusted. Every change here was a debt against that
trust.

---

## Sprint F — Daily-use polish

### Problem the session uncovered

A user synced Gmail, asked the agent a question whose answer was in their
inbox, and got "I don't have information about that." The integrations page
said "Gmail · Synced." Everything looked fine.

After an extended debug session it turned out:

1. Migrations 011–015 had never been applied to the running Postgres.
2. The ConnectorIndexer was failing silently — Weaviate write errors got
   logged as warnings and the row's `embedding_status` was left untouched.
3. The frontend hid the existence of "indexed" entirely; it just showed
   "Synced" or "Not connected."
4. The orchestrator's `tool_planner_node` was passing prior assistant turns
   to the LLM as `SystemMessage` instead of `AIMessage`, so the model had
   no real conversational memory across turns.

The user's lived experience was: "I synced, I'm asking, it's failing, why?"

### What we built

**Index-failure observability.** Migration `015_source_items_embedding_error.sql`
adds an `embedding_error TEXT` column. `ConnectorIndexer` now writes
`status='failed'` plus the truncated exception message on every failure,
and emits a telemetry row.

**A reindex endpoint.** `POST /api/connectors/{source}/reindex` pulls up
to 200 stuck rows, calls `ConnectorIndexer.index()` per item, and on success
flips the row to `'indexed'`. No ESL gate — it's operational, matching the
`tool_telemetry.record_tool_call` precedent.

**Status footer on the integrations page.** Per-connector tile shows
`indexed / failed / pending` counts plus the last error message and a
Reindex button. Hides cleanly when there's nothing synced yet.

**Cross-source Today feed.** `/api/today/feed` aggregates tasks + recent
emails + recent Slack + calendar-today into one rectangle. Smart empty
states based on which connectors are actually wired.

**Planner bias.** The `search_documents` tool description got five sample
query phrasings ("what did X say about Y", "find the email about Z", …)
and the system prompt added a recall-bias bullet. Five regression tests
pin this so the bias doesn't drift.

**The blank-chat bug.** Sending the first message on `/dashboard/chat`
used `router.replace('/dashboard/chat/<id>')` to update the URL. That
unmounted the streaming component on its way to `/chat/[id]/page.tsx`,
dropping the in-flight stream. Switched to `window.history.replaceState`
so the current component keeps streaming.

**The conversation-memory bug.** One-line fix: `SystemMessage` →
`AIMessage` for replayed assistant turns. Suddenly the agent referenced
"Catia" by name across messages.

**Error-noise sweep.** Three toasts that triggered on routine navigation
got demoted to `console.error`. The screen stopped flashing red on every
refetch.

### Verification

End-to-end test: uploaded a real M-KOPA recruiting email via Gmail sync,
asked "what was that Welcome to the Jungle email about?", got back the
sender, subject, role, location, and description — cited.

---

## Sprint G — Retrieval depth + ops safety net

### Why this came next

Sprint F proved retrieval worked. Two follow-ups were obvious:

1. The debug session itself cost hours because migrations had silently
   drifted from the code. That foot-gun had to die.
2. Hybrid search returned reasonable candidates but ranking was
   fusion-only. A reranker pass would tighten top-K and let the LLM see
   five really-relevant chunks instead of fifteen okay ones.

Plus uploaded PDFs/DOCX were second-class — only plain text got chunked,
so binary uploads were dead weight.

### What we built

**Auto-run migrations on startup.** Lifespan hook calls `run_migrations()`
after the DB pool is ready, before the scheduler starts. Logs
`applied N migration(s)` or `schema up to date`. If a migration raises,
the backend refuses to start — fail-loud, fix-forward. The runner was
already idempotent via a `schema_migrations` tracking table; just had
to fire it on boot.

**PDF/DOCX ingestion.** New `services/document_extractors.py` with a
single `extract_text(file_path, mime_type) -> str` entry point. Lazy
imports `pypdf` and `python-docx` so cold-starts don't pay for them.
`document_processor.py` writes upload bytes to a temp file with the
proper suffix and delegates to `extract_text` — the existing chunker
consumes the same string regardless of source.

**Jina cross-encoder rerank.** `services/rerank.py` exposes
`rerank(query, candidates, *, top_k=5, ...)`. It calls
`https://api.jina.ai/v1/rerank` with `jina-reranker-v2-base-multilingual`.
On missing key, HTTP error, or malformed response, it returns
`candidates[:top_k]` unchanged with a debug log. `RagRetrievalService`
now widens hybrid search to top-20 internally then routes through
`rerank`. The public `retrieve()` signature didn't change.

Why Jina over Cohere: free tier is 100 RPM / 100K TPM with no monthly
cap, vs Cohere's 1000-requests-per-month / 10 RPM / non-commercial-only.

**Retrieval breadcrumbs in Transparency.** `retrieve_with_trace()`
returns the result list alongside a `trace` dict — query, all hybrid
candidates with scores, whether rerank was applied, rerank scores when
it was, and which chunk_uuids made the final cut. The
`search_documents` tool folds the trace into `tool_call_events.output`,
and the Transparency tab renders it as a "Retrieval trace" section
with final-cited chunks highlighted green in the candidate list.

### Hotfix mid-sprint: clicking anywhere spawns a new conversation

After Sprint F shipped, the user reported:

> "deal with it keeping starting conversations whenever I do something
> or click anywhere"

Root cause: the Sprint F replaceState fix kept the streaming component
mounted across the URL change, but the component read `conversationId`
from the route segment prop — which `replaceState` doesn't refresh.
Every subsequent send saw `conversationId === undefined` and called
`conversations.create()` again. Sidebar/header `if (conversationId)
router.replace(...)` checks also no-op'd while the URL still showed
`/chat/<id>`.

Fix: track the active id in local state seeded from the prop, update
it after creating a conversation, clear it (with a replaceState
fallback to scrub the stale URL) on the New-chat reset path. Three
references across the file collapsed to one source of truth.

### Verification

* Backend: 440 passed, 2 skipped.
* Frontend: `tsc --noEmit` clean.
* Real Jina API call returned tighter, more relevant top-5 on the
  M-KOPA query than raw hybrid did.
* Without `JINA_API_KEY` set, retrieval still works on raw hybrid
  (graceful fallback verified by `test_rerank.py`).

---

## Sprint H — First-run onboarding

### Why this was the next biggest user-felt gap

Every other sprint assumed a populated account. A genuine first login
landed on:

* Today — empty (no connectors)
* Chat — no values to ground anything on, the ESL has nothing to gate
* Dashboard — no goals, no projects
* Settings — sources unconnected, values blank

The agent had nothing to work with, the ESL had no boundaries to enforce,
and the user had no signal of what to do first. The whole "trust over
engagement" affordance is moot when `user_values` is empty.

### Architecture decision: one flag, three derived booleans

Considered a multi-step state machine. Rejected. The underlying tables
(`data_sources`, `user_values`, `goals`) are already the source of
truth for what got done. A separate state machine would drift.

Settled on a single nullable timestamp:

```sql
ALTER TABLE public.users ADD COLUMN onboarded_at TIMESTAMPTZ NULL;
```

Set when the user finishes the wizard or explicitly skips. The three
"has X yet?" flags are computed live via `EXISTS` against the existing
tables — no separate state to maintain.

### What we built

**Backend** (`routes/onboarding.py`):
* `GET /api/onboarding/state` → `{ onboarded_at, has_data_source,
  has_value, has_goal }`. Single query with three EXISTS subselects.
* `POST /api/onboarding/complete` → `UPDATE users SET onboarded_at =
  COALESCE(onboarded_at, NOW())`. Idempotent.
* `/api/auth/me` extended to include `onboarded_at` so the frontend
  can route on first paint without a second roundtrip.

**Wizard** at `/onboarding`, own route (not a modal):
1. Connect a source — Gmail / Calendar / Slack rows with inline
   Connect buttons reusing existing OAuth start endpoints.
2. Declare values — three text inputs labeled "Something you want
   the assistant to honor," with example placeholders. Non-empty
   inputs POST to `user_values` as type=`boundary`, priority=5.
3. Seed a goal — title + optional date.

Each step is skippable. Final "You're set" screen → `/dashboard/today`.

**Redirect guard** in `app/dashboard/layout.tsx`: if
`onboarded_at IS NULL` AND has-no-data-source AND has-no-value AND
has-no-goal, redirect to `/onboarding`. The triple-AND is intentional:
a returning user who skipped earlier and has since added even one
value by hand is *not* re-trapped. The data is the source of truth.

**Sidebar nudge** for the in-between state: a small "Finish setting
up · N of 3 done" tile above the primary nav. Dismissable per-browser
via localStorage; reappears on another device if setup is still
incomplete.

### Quirk worth knowing

OAuth callbacks land on `/dashboard/integrations`, not back in the
wizard. The existing `/api/data-sources/oauth/{type}/authorize`
endpoint doesn't accept a `return_to` param. Worked around it with a
localStorage marker (`ec_onboarding_in_progress`) and a "Continue
setup →" banner on the integrations page. Patching the backend for a
cleaner return is a small follow-up.

---

## Patterns worth keeping

A few decisions in this session that felt like they paid off:

**One flag plus derived booleans beats a state machine.** Sprint H's
onboarding had the obvious "should this be a state machine?" question
sitting in front of it. The data is already the source of truth;
duplicating it into a state column would drift. One nullable timestamp
+ three live EXISTS queries was the smaller, more honest design.

**Graceful fallback over hard dependency.** Sprint G's rerank works
without `JINA_API_KEY`. Sprint H's `/me` endpoint logs and continues
if it can't load `onboarded_at`. Every external dependency this
session touched got a "what if it's missing or broken?" path.

**Fail-loud where silence costs you hours.** Auto-run migrations
re-raise on failure. The backend refuses to start. This is the
opposite of the previous Sprint F bug (silent indexer failures) and
it's deliberate — silence was the original sin.

**Symptoms back to root causes.** "When I type hello it opens a
blank chat" became `router.replace` unmounting a streaming component.
"It keeps starting new conversations" became a prop that doesn't
refresh under `replaceState`. "I synced and it can't find anything"
became silent migration drift plus silent indexer failure. None of
these were "add a feature" — they were "find the lie the system was
telling and fix it."

**Subagents for breadth, direct for depth.** Sprint G Task 4
(breadcrumbs across backend + frontend + tests) and Sprint H Task 2
(wizard with three step components) went to subagents. The
single-file fixes — the conversation-id hotfix, the redirect guard,
the sidebar nudge — stayed in the main thread. Roughly: dispatch when
the work spans 5+ files; stay in-thread when you need to feel the
codebase.

---

## Verification at the close

```bash
$ cd backend && pytest --tb=short -q
444 passed, 2 skipped, 7 warnings in 5.55s

$ cd ../frontend && npx tsc --noEmit
(clean)
```

End-to-end manually verified: fresh login → wizard → connect Gmail →
declare two values → seed one goal → land on Today with content →
ask "what was that M-KOPA email about" → get a cited answer pulled
from real inbox content.

---

## What's not done

Things we deliberately deferred so the sprints stayed focused:

* **Rerank eval harness** with a fixed query set scoring recall@5.
  Ship the rerank, measure with real usage, decide if a harness is
  needed.
* **Per-project document scoping** in chat. Needs a project-picker
  UI; own micro-sprint.
* **Scheduler observability** — `scheduled_job_runs` table + a System
  Health row + alerting on consecutive failures. The natural fourth
  ops-safety sprint.
* **OAuth `return_to` support** so the wizard doesn't need the
  localStorage detour. Two files, half an hour.
* **OCR for image-only PDFs.** pypdf returns empty for them; we
  accept that and warn.

The plans are sitting in `docs/plans/2026-04-27-sprint-{f,g,h}-*.md`
for the next session to pick up.
