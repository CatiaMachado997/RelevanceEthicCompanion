# Ethic Companion — Revised Roadmap V2: Industry-Standard Foundation
**Spec Date:** 2026-03-28
**Status:** Approved (rev 2 — post spec review + new features)
**Author:** Brainstorming session with user

---

## Supersedes

**`docs/plans/2026-03-28-sprint-2-connector-framework.md` is deprecated by this document.**

The custom `BaseConnector` ABC (`backend/services/connectors/base.py`, `gmail.py`, `google_calendar.py`, `slack.py`) will be deleted at the start of Sprint 2b. The OAuth token management and sync logic inside those files will be ported into MCP server modules — preserving the business logic while replacing the proprietary interface with MCP-standard tool definitions. Do not implement the `BaseConnector` interface.

---

## Overview

This document revises the master product roadmap to incorporate industry-standard tooling (MCP, LangGraph, Langfuse, Skills registry, WebSocket) and expands the Chat as Workspace phase with new features: deep research mode, multimodal file insertion, explicit web search, full plan-in-chat workspace, task scheduling intelligence, and an Information Overload Breakdown mode. It also adds a dedicated Frontend Polish sprint and elevates auth/settings/user status to a first-class concern.

**Core philosophy unchanged:** Trust over Engagement. ESL remains a mandatory gateway for all user-facing actions throughout every phase.

---

## Problem Statement

The existing roadmap (v1) had five structural gaps:

1. **Custom connector framework** — Sprint 2 planned a proprietary `authorize/sync/normalize` adapter interface. This becomes technical debt as MCP (now industry standard with 97M+ monthly downloads) matures. Every connector would need rebuilding later.

2. **Bypassable ESL** — `orchestrator_v2.py` calls `evaluate_action()` as a function call. Nothing structurally prevents a future developer from skipping it. ESL must be architecturally enforced as a graph node.

3. **No observability** — A trust-first product has no LLM tracing, token cost monitoring, or tool success tracking. It is impossible to prove the system is behaving correctly.

4. **Weak auth/session UX** — Login page, session persistence (cookies + cache), settings, and user status are incomplete. Users experience auth disruption between sessions.

5. **Frontend gaps** — Dashboard, chat page, and minor UI elements have known broken states. These need a focused sprint before the roadmap proceeds.

---

## New Features Added (vs. V1 Roadmap)

| Feature | Sprint |
|---------|--------|
| LangGraph orchestrator rewrite | 2a |
| FastAPI-MCP server | 2a |
| Skills registry (YAML) | 2a |
| Langfuse observability | 2a |
| Auth hardening (cookies, cache, secure session) | 2a |
| Settings page overhaul | 2a |
| User status system | 2a |
| Frontend Polish sprint (dashboard + chat + login) | 2a |
| Connectors as MCP servers | 2b |
| Multimodal file insertion in chat | 3 |
| RAG reranker | 3 |
| Make plans in chat (full workspace) | 4 |
| Task scheduling intelligence | 4 |
| Letta-style memory blocks | 5 |
| Information Overload Breakdown mode | 5 |
| Deep research mode (quick + deep) | 6 |
| Web search (explicit first-class) | 6 |
| WebSocket bidirectional transport | 6 |

---

## Approach: Foundation Sprint + MCP-Native Connectors

Insert **Sprint 2a (Foundation + Frontend Polish, 2 weeks)** before the connector work. This sprint: rewrites the orchestrator in LangGraph, wraps all FastAPI routes as MCP tools, adds Langfuse observability, hardens auth/session management, overhauls the settings page, adds user status, and fixes known frontend gaps.

Every phase after 2a builds MCP-native — connectors as MCP servers, documents as MCP resources, tasks as MCP resources, tools as YAML-described skills.

**Result:** By Sprint 6, the orchestrator discovers and calls everything through MCP. Adding a new tool = one YAML file. No orchestrator code changes.

---

## Revised Phase Map

| Sprint | Weeks | Focus | Status |
|--------|-------|-------|--------|
| Sprint 1 | 1–2 | Stabilization | In progress |
| **Sprint 2a** | 3–4 | **Foundation + Auth + Frontend Polish** | New |
| Sprint 2b | 5–6 | Connections as MCP servers | Replaces old Sprint 2 |
| Sprint 3 | 7–8 | Documents + File insertion | Updated |
| Sprint 4 | 9–10 | Projects, Tasks, Plans in Chat | Updated |
| Sprint 5 | 11–12 | 360° Context + Information Overload Breakdown | Updated |
| Sprint 6 | 13–14 | Chat as Workspace (Research, Search, Multiagent) | Heavily expanded |
| Sprint 7 | 15+ | Proactive Intelligence | Post-MVP |

---

## Sprint 2a: Foundation + Auth + Frontend Polish (New — Weeks 3–4)

**Goal:** Clean architectural foundation, hardened auth/session, polished frontend. No new user-visible features beyond auth/settings/UI fixes.

**Workstream priority order** (for scope management if sprint runs long):
- **Blocking for Sprint 2b** (must complete): A (LangGraph orchestrator), B (FastAPI-MCP), E (auth hardening), G (user status + schema migration)
- **Best-effort** (can spill into start of Sprint 2b): C (skills registry), D (Langfuse), F (settings overhaul), H (frontend polish)

If Workstream A is not complete and passing regression tests by end of day 8, defer Workstreams F and H entirely to Sprint 2b and focus the remaining time on A + E.

**Step 0 — Install dependencies before writing any code:**
```bash
# Add to backend/requirements.txt, then:
pip install langgraph>=0.2.0 fastapi-mcp>=0.4.0 langfuse>=2.0.0
# anthropic, cohere/sentence-transformers, openai-whisper added in their respective sprints
```

---

### Workstream A — LangGraph Orchestrator (full rewrite)

`backend/services/orchestrator_v2.py` (914 lines) is replaced by `backend/orchestrator/graph.py`.

**Pre-rewrite step (test-first):** Before touching `orchestrator_v2.py`, write a regression test suite covering `/api/chat/stream` end-to-end: user sends message → tokens stream → done event received → conversation stored. This test suite runs against the old orchestrator first (baseline), then against the new LangGraph orchestrator (must pass identically).

**Graph structure:**
```
UserInput
  → ContextBuilder          # Assembles M1 + M2 context
  → IntentClassifier        # Routes: chat / research / plan / search / file
  → ToolPlanner             # Calls list_tools() from MCP registry
  → ToolExecution (loop)    # Executes tools, max 5 rounds
  → ESLGateway              # MANDATORY node — every path passes through ESL
      ↓ APPROVED
  → ResponseFormatter       # Structures output (text / artifact / card)
      ↓ VETOED
  → ExplainVeto             # Returns ESL reason to user
      ↓ MODIFIED
  → ApplyModification → ResponseFormatter
  → Output (SSE stream, same AsyncGenerator interface as current)
```

**Key properties:**
- ESL is a graph node — structurally impossible to bypass
- Typed `AgentState` dataclass carries context, decision, tool results through every node
- Token budget tracking ported from `orchestrator_v2.py` (existing 75%/85% warning logic, not reimplemented)
- SSE streaming interface preserved: `/api/chat/stream` route in `backend/routes/chat.py` unchanged
- Conversation history stored after every graph run (port of `_post_stream_store`)

**File layout:**
```
backend/orchestrator/
  graph.py          # StateGraph definition
  state.py          # AgentState typed dict
  nodes/
    context.py      # ContextBuilder node
    intent.py       # IntentClassifier node
    tools.py        # ToolPlanner + ToolExecution nodes
    esl.py          # ESLGateway node (wraps existing esl/engine.py)
    response.py     # ResponseFormatter node
  subgraphs/        # Created empty — subgraphs added per sprint
    __init__.py
```

**Note:** `deep_research.py` and `task_scheduler.py` subgraphs are NOT created in Sprint 2a. They are added in their respective sprints (6 and 4) to avoid broken imports.

**Migration path:**
1. Write regression tests against `orchestrator_v2.py`
2. Create `backend/orchestrator/` alongside existing file (do not delete yet)
3. Add feature flag `USE_LANGGRAPH=true` in `.env` — `chat.py` route selects orchestrator
4. Run regression tests against LangGraph orchestrator (must pass)
5. Delete `orchestrator_v2.py` and remove feature flag
6. Port or delete `tests/test_orchestrator_v2.py` to match new structure

---

### Workstream B — FastAPI-MCP Server

**Transport model:** All connectors run in-process within the FastAPI application. `fastapi-mcp` exposes existing FastAPI routes as MCP tools via HTTP transport (not stdio sidecar processes). "MCP server" throughout this spec means a logical MCP namespace exposed via the FastAPI-MCP layer — not a separate process.

OAuth tokens remain in PostgreSQL, accessed by all MCP tools through the shared DB connection pool. No separate credential sharing infrastructure needed.

```python
# backend/main.py — single addition
from fastapi_mcp import FastApiMCP
mcp = FastApiMCP(app)
mcp.mount()
```

All existing FastAPI routes become discoverable MCP tools. The ToolPlanner calls `list_tools()` at startup.

**New dependency:** `fastapi-mcp>=0.4.0` — already added in Step 0 above.

**Sprint 2a schema addition for ESL models** — add `SLACK_SEND` to `ActionType` enum in `backend/esl/models.py` now (not Sprint 2b), so Skills YAML files referencing `esl_action_type: slack_send` validate correctly at startup:
```python
# backend/esl/models.py — ActionType enum
SLACK_SEND = "slack_send"   # add alongside EMAIL_SEND
```

---

### Workstream C — Skills Registry

```
backend/skills/
  web_search.yaml
  query_memory.yaml
  query_calendar.yaml
  get_user_goals.yaml
  create_note.yaml
```

Each YAML: `name`, `description`, `mcp_tool`, `parameters`, `esl_action_type`, `requires_confirmation`. ToolPlanner loads skills at startup. Adding a capability = new YAML file, zero `graph.py` changes.

---

### Workstream D — Langfuse Observability

**New dependency:** `langfuse>=2.0.0` — already added in Step 0 above.

**Deployment choice (decide before Sprint 2a):** Cloud Langfuse (langfuse.com — free tier available) or self-hosted Docker container (add `langfuse` service to `docker-compose.yml`). Recommendation: cloud for MVP speed, self-hosted for production/compliance.

Langfuse SDK wraps every:
- LLM call (model, tokens, latency, cost)
- Tool execution (name, success/fail, duration)
- ESL decision (status, reason, confidence, violated values)

ESL audit log entries correlated with Langfuse trace IDs — full decision lineage in one place.

---

### Workstream E — Auth Hardening + Secure Session

**Current gaps:** Session state is lost on page refresh. Auth token is stored in `localStorage` (XSS-vulnerable). Settings don't persist reliably between sessions.

**Fixes:**

1. **HttpOnly cookies for JWT** — Move Supabase session token from `localStorage` to `HttpOnly; Secure; SameSite=Strict` cookie. XSS cannot access HttpOnly cookies. Backend reads `Authorization` header OR cookie (both supported for API client flexibility).

2. **Session persistence with cache** — On sign-in, store non-sensitive user state (display name, avatar URL, theme preference, last active route) in `localStorage` for instant UI hydration. Sensitive tokens only in HttpOnly cookie. On app load: read cookie (auth) + localStorage (display state) simultaneously — no auth flicker.

3. **Supabase RLS enforcement** — Verify all PostgreSQL tables enforce `auth.uid() = user_id` Row Level Security policies. Add missing RLS policies where absent.

4. **Auto-refresh** — Supabase client auto-refreshes JWT before expiry. Backend validates token signature on every request.

5. **Secure logout** — Clears cookie, clears localStorage, invalidates Supabase session.

---

### Workstream F — Settings Page Overhaul

**Current state:** Settings page exists but updates are unreliable and the UI is sparse.

**New settings page sections:**

| Section | Contents |
|---------|----------|
| Profile | Display name, avatar, timezone, language |
| Notifications | Email, push, ESL alerts — per-channel toggles |
| Privacy | PII protection, share analytics, data retention |
| ESL Weights | Goal alignment, time sensitivity, personal values, context relevance sliders |
| Connections | Connected integrations (link to Integrations page) |
| Security | Active sessions list, sign out all devices, delete account |
| Appearance | Theme (light/dark/system), font size |

**Persistence:**
- Sections Profile / Notifications / Privacy / ESL Weights persist via `PUT /api/settings/` (ESL-gated). Optimistic UI update with rollback on error.
- Section Connections links to Integrations page — no direct settings write.
- Section Security (sign out all devices, delete account) uses dedicated auth endpoints.
- Section Appearance (theme, font size) is **localStorage-only** — stored client-side under key `ec_appearance`, never sent to backend. No schema migration needed. On load, frontend reads `ec_appearance` before first render to prevent theme flicker.

Settings loaded on dashboard init and cached in memory for the session. `PUT /api/settings/` schema additions required for Profile fields (timezone, language) — add `timezone TEXT` and `language TEXT` columns to `user_settings` table in `backend/database/schema.sql`.

---

### Workstream G — User Status System

**What it is:** A persistent status indicator (like Slack's status) showing the user's current mode. Visible in the sidebar/nav bar.

**Status options:**
- `available` — normal mode (default)
- `focus` — focus mode on; ESL blocks non-critical interruptions
- `do_not_disturb` — quiet hours override; all proactive suggestions suppressed
- `away` — low-activity mode; digest-only notifications

**Implementation:**

**Schema migration** — create `backend/database/migrations/sprint2a_status.sql`:
```sql
ALTER TABLE public.user_settings
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'focus', 'do_not_disturb', 'away')),
    ADD COLUMN IF NOT EXISTS status_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS timezone TEXT,
    ADD COLUMN IF NOT EXISTS language TEXT;
```
Also update `backend/database/schema.sql` and `schema_local.sql` to include these columns.

**API endpoint:** Status changes go to a dedicated `PUT /api/status/` endpoint (not `/api/settings/`). This endpoint is **not ESL-gated** — the user is directly controlling their own mode state. It writes `status` and `status_until` to `user_settings`. The ESL context builder reads these columns as part of `get_user_context()`.

- Quick-change popover in sidebar (click avatar → set status + optional duration)
- ESL reads `status` column: `focus` → enables focus mode; `do_not_disturb` → enforces quiet hours regardless of time; `away` → suppresses all proactive suggestions
- Status badge visible in dashboard header and settings

---

### Workstream H — Frontend Polish

Known broken/incomplete states to fix in this sprint:

**Login page:**
- Visual redesign: clean centered card, Ethic Companion logo/wordmark, Google OAuth button, email/password fallback
- Auth error messages (currently silent failures)
- "Remember me" checkbox (extends cookie TTL to 30 days vs. session)
- Redirect to last active route after sign-in (stored in localStorage before redirect)
- Loading state during OAuth handshake

**Dashboard page:**
- Empty states for all widgets (Goals, Tasks, Integrations) when no data exists
- Skeleton loaders during data fetch
- Error boundary with retry button
- ESL status ambient indicator (subtle pulse in sidebar when ESL is active)

**Chat page:**
- Fix: streaming cursor sometimes sticks after `done` event
- Fix: model selector menu z-index (hidden behind other elements)
- Fix: rate limit warning dismissed but reappears on next message
- Fix: conversation history doesn't reload on page refresh
- Improve: ESL badge collapse animation
- Add: keyboard shortcut legend (Cmd+Enter, Escape, etc.)

**WebSocket — deferred to Sprint 6** (Sprint 2a scope reduction per spec review S5). Sprint 2a keeps SSE. WebSocket endpoint added in Sprint 6 when bidirectional agent control is needed.

---

### Sprint 2a Acceptance Criteria

- [ ] Regression test suite for `/api/chat/stream` passes against new LangGraph orchestrator
- [ ] ESL decisions appear in both audit log and Langfuse traces
- [ ] All existing API routes discoverable via MCP `list_tools()`
- [ ] New skill added via YAML without touching `graph.py`
- [ ] JWT stored in HttpOnly cookie; auth survives page refresh
- [ ] Settings changes persist and reload correctly on next session
- [ ] User status toggle works and is read by ESL context builder
- [ ] Login page redesign live with error handling and redirect
- [ ] Dashboard empty states, skeleton loaders, error boundaries in place
- [ ] Chat page streaming cursor, model selector, rate limit, and history bugs fixed

---

## Sprint 2b: Connections as MCP Servers (Weeks 5–6)

**Goal:** Build Calendar, Gmail, Slack as MCP-namespaced tools. Delete old `BaseConnector` code.

**Start of sprint:** Delete `backend/services/connectors/base.py`, `gmail.py`, `google_calendar.py`, `slack.py`. Port OAuth token logic into new MCP tool modules.

**MCP namespaces (all in-process via FastAPI-MCP):**

```
calendar tools:
  list_events, create_event, update_event, delete_event, find_free_slots

gmail tools:
  list_messages, get_message, send_message, search_messages, create_draft

slack tools:
  list_channels, get_messages, send_message, search_messages
```

**ESL action types:**
- `create_event`, `update_event`, `delete_event` → `CALENDAR_WRITE`
- `send_message` (gmail) → `EMAIL_SEND`
- `send_message` (slack) → `SLACK_SEND` *(enum value added in Sprint 2a Workstream B)*
- All read operations → `CONTENT_GENERATION` (advisory ESL check)

**Normalized ingestion:** Every connector writes to `source_items` table via shared `IngestionService`. Schema: `source_type, external_id, title, body, metadata, embedding_status, sensitivity` (matches live `source_items` table column name).

**Sync observability UI:** Integrations page shows connection status, last sync, item counts, health, disconnect/resync controls.

**Acceptance criteria:**
- Calendar sync: events → `source_items` → indexed in Weaviate
- Gmail sync: last 7 days inbox → normalized + indexed
- Slack sync: recent messages from connected channels → normalized + indexed
- `SLACK_SEND` already in `ActionType` enum (added Sprint 2a); Slack sends ESL-gated
- Old `BaseConnector` files deleted
- Integrations page shows live sync health per connector

---

## Sprint 3: Documents (Weeks 7–8)

**Goal:** Documents as a first-class product surface and multimodal file input in chat.

**Ingestion pipeline:**
```
Upload → ExtractText (pypdf / python-docx) → Chunk (512 tokens, 20% overlap)
  → Embed (Google Gemini) → Weaviate index
  → ESL sensitivity check → PostgreSQL (documents + document_chunks tables)
```

**Retrieval (upgraded RAG):**
```
Query → Dense vector search + BM25 sparse search (hybrid)
  → Retrieve top-50 candidates
  → Cross-encoder reranker → top-10
  → Feed to LLM with inline citations
```

**Reranker dependency:** `sentence-transformers>=2.2.0` (BAAI/bge-reranker-v2-m3, ~270MB model download — note in deployment docs) OR Cohere Rerank API (hosted, no local model). Decision: Cohere for MVP (no infra), sentence-transformers for self-hosted production. Add chosen library to `requirements.txt`.

**MCP namespace:**
```
document tools:
  upload_document, search_documents, get_document_chunk, extract_tasks_from_doc

document resources:
  documents://library, documents://doc/{id}
```

**File insertion in chat (multimodal):**
- Drag-and-drop or paperclip icon in chat input
- Supported: PDF, DOCX, TXT → extracted + chunked; PNG/JPG/WEBP → vision analysis (Gemini Vision); MP3/WAV → Whisper transcription
- Multi-file drop supported in single message
- File processed inline for conversation AND ingested to Documents library
- ESL `data_collection` check before ingestion
- AI can immediately answer questions, extract tasks, summarize, link to project

**Acceptance criteria:**
- Upload PDF → ask questions → answers cite specific chunks
- Image in chat → AI describes and extracts text
- Audio in chat → transcribed via Whisper → AI responds to content
- Reranker improves retrieval precision (manual test: top-10 vs. top-50 comparison)
- All ingested files appear in Documents library, searchable

---

## Sprint 4: Projects & Tasks (Weeks 9–10)

**Goal:** Full work management surface with AI-powered plan creation and task scheduling.

**Data model:**
```
Goals (intentions, user-defined)
  └── Projects (containers with deadline + status)
        └── Tasks (title, status, priority, due_date, source_origin,
                   project_id, doc_links, ai_confidence, user_confirmed)
```

**MCP namespaces:**
```
project tools:
  create_project, update_project, list_projects, link_task, link_document

task tools:
  create_task, update_task, confirm_task, list_tasks, extract_tasks_from_source
  resources: tasks://today, tasks://overdue, tasks://by_project/{id}
```

**Make Plans in Chat — PlanBuilder node:**

Triggered by `/plan` command or intent detection. Implemented as an orchestrator node (not a subgraph — single-pass with structured output).

```
PlanBuilder node:
  1. Parse plan request (scope, deadline, goal linkage)
  2. LLM generates: milestones, tasks, dependencies, time estimates
  3. Align tasks to active Goals by ESL-weighted alignment score
  4. Return structured PlanArtifact (JSON → rendered as interactive card)
```

**PlanArtifact interaction:**
- "Save as Project" → creates Project + all Tasks via MCP tools (ESL-gated)
- Calendar blocks suggested for focus time (user must confirm — never auto-written)
- AI stays in conversation — "move milestone 2 to next week" re-runs PlanBuilder node with amendments
- All task creation and calendar writes gated by ESL (`data_collection` + `CALENDAR_WRITE`)

**Task Scheduling Intelligence — TaskScheduler subgraph:**
```
backend/orchestrator/subgraphs/task_scheduler.py

TaskScheduler subgraph:
  ReadOpenTasks → ReadCalendar (find_free_slots) → ReadGoalPriorities
  → RankTasks (goal_alignment × urgency × available_time score)
  → ProduceWeeklyPlan (structured artifact)
  → ESLGateway (quiet hours + focus mode check)
  → Output WeeklyPlanArtifact
```

Triggered by `/organize` or "organize my tasks" in chat. User can drag to reorder, confirm to lock calendar blocks. No calendar writes without user confirmation.

**Acceptance criteria:**
- `/plan` produces PlanArtifact, "Save as Project" creates real Project + Tasks
- Tasks link to Goals with visible alignment score
- `/organize` produces ranked weekly schedule respecting calendar + goal priorities + quiet hours
- Task extracted from email/Slack appears with `ai_confidence` and confirmation prompt
- All task/project writes ESL-gated

---

## Sprint 5: 360° Context + Information Overload Breakdown (Weeks 11–12)

**Goal:** Explicit, correctable user context model and a new breakdown mode for information overload.

---

### Letta-Style Memory Upgrade

**Core memory blocks** (always injected into system prompt):
```
persona_block:    user's role, working style, communication preferences
goals_block:      current top 3 goals with priorities
boundaries_block: active values and quiet hours
focus_block:      current focus mode / status
```

**Archival memory** (Weaviate, retrieved on relevance):
- Past conversations, processed documents, extracted insights and decisions

**Memory write trigger:** After each graph run, the ResponseFormatter node evaluates whether any new facts warrant updating a core memory block. If yes, it emits an `update_memory_block` tool call. The `update_memory_block` MCP tool is ESL-gated (`data_collection`) before writing.

**`user_context_snapshot` service:** Computed after every sync, conversation, feedback event, or task change. Sections: `focus_now`, `active_projects`, `urgent_items`, `recent_decisions`, `calendar_pressure`, `values_and_boundaries`, `recommended_next_actions`.

**MCP namespace:**
```
context tools:
  update_memory_block, correct_assumption, get_context_explanation
context resources:
  context://snapshot, context://memory/core, context://memory/archival
```

**UI:** "Your context" panel on dashboard. "Why I think this matters" on every suggestion. User corrects assumptions inline.

---

### Information Overload Breakdown Mode

**What it is:** A dedicated mode (accessible from sidebar nav and chat `/breakdown` command) that rapidly surfaces what's competing for the user's attention across all connected sources — inbox, calendar, Slack, tasks, documents — and organizes it into actionable topic clusters.

**Problem it solves:** The user has 200 unread emails, 50 Slack messages, 10 open tasks, and 5 upcoming meetings. It's overwhelming. This mode does the triage for them.

**OverloadBreakdown subgraph:**
```
backend/orchestrator/subgraphs/overload_breakdown.py

OverloadBreakdown subgraph:
  ParallelIngestion node:
    → Executes all five fetches concurrently via asyncio.gather()
    → FetchInbox (gmail MCP: unread messages, last 48h)
    → FetchSlack (slack MCP: unread messages, last 48h)
    → FetchCalendar (calendar MCP: next 7 days events)
    → FetchOpenTasks (tasks MCP: overdue + due this week)
    → FetchRecentDocs (documents MCP: recently modified)
    → Timeout per source: 5 seconds. Slow/failed sources return partial result
      with error flag; BreakdownArtifact surface source error badges for these.

  ESLTopicFilter node (immediately after ParallelIngestion):
    → Apply user's blocked topic filters to ALL raw items before any LLM call
    → Remove matching items entirely (never fed to LLM — prevents content leaking
      into cluster titles via summarization)
    → Log filtered items to esl_audit_log

  TopicExtraction node:
    → LLM extracts topic clusters from filtered items
    → e.g., "Project X deadline", "Budget sync", "Vendor proposal review"
    → Each item tagged with: topic, urgency, source, estimated_effort

  PriorityRanking node:
    → Score each cluster: goal_alignment × urgency × item_count
    → No additional ESL check here (filter already applied above)

  Output: BreakdownArtifact
    → Topic clusters ranked by priority
    → Each cluster: title, item count, sources, urgency, suggested next action
    → Source error badges for any timed-out connectors
    → Actions: "Start chat about this" | "Create task" | "Schedule focus time" | "Dismiss"
```

**UI — Breakdown view:**
- Accessible from sidebar as "Breakdown" or via `/breakdown` in chat
- Renders as a kanban-style priority board: columns = urgency levels (Critical / This Week / Later)
- Each card = a topic cluster with source badges (Gmail icon, Slack icon, Calendar icon, etc.)
- Click card → opens a scoped chat session pre-loaded with all items in that cluster
- "Create tasks from this cluster" → extracts tasks via TaskManager (ESL-gated, confirmation required)
- ESL: topic filter applied to all clusters before display; manipulation/FOMO language stripped from summaries

**Acceptance criteria:**
- `/breakdown` produces BreakdownArtifact within 30 seconds when all connectors respond within 5 seconds
- Slow or failed connectors show source error badges; partial results still render
- Topic clusters are coherent (not just keyword groups)
- Clusters ranked by goal alignment + urgency correctly
- Blocked topics (from user values) not surfaced and not fed to LLM
- Clicking a cluster opens scoped chat with relevant items loaded

---

## Sprint 6: Chat as Workspace (Weeks 13–14)

**Goal:** Chat becomes the primary command surface. All modes unified under intent routing.

### WebSocket Transport (added here, per spec review scope reduction)

WebSocket endpoint at `/api/chat/ws` added alongside SSE.

| Transport | Use case |
|-----------|----------|
| SSE | Simple token streaming (existing chat, default) |
| WebSocket | Cancel mid-generation; human-in-the-loop approval; real-time tool status |

Frontend upgrades to WebSocket when agent actions require user confirmation (calendar writes, task creation, sends).

### LLM Routing (Groq + Claude)

| Intent | LLM |
|--------|-----|
| `chat`, `search` | Groq Llama 3.3 70B (fast, low cost) |
| `research_deep`, `plan` | Anthropic Claude Sonnet (better long-horizon reasoning) |
| `organize`, `breakdown` | Groq Llama 3.3 70B (structured output) |
| Embeddings | Google Gemini (unchanged) |

### Deep Research Mode

**Quick mode (default):** 3–5 parallel Tavily searches, synthesized with citations, ~30 seconds, Groq.

**Deep mode (toggle in chat toolbar):** DeepResearch subgraph, Claude Sonnet:

```
backend/orchestrator/subgraphs/deep_research.py

DeepResearch subgraph:
  PlanQueries → [Parallel Search × N] → ReadSources → EvaluateCoverage
    → GapDetected? → RefineQueries → [loop, max 3 iterations]
    → CrossReference (user's docs + calendar + goals via MCP)
    → ProduceReport (Research Report artifact: sections + citations)
```

Output: **Research Report artifact** — collapsible sections, inline citations, "Save to Documents", "Extract Tasks".

### Web Search (explicit first-class mode)

`/search` command or search icon. User sees queries, sources, final answer with source cards. ESL topic filter applied to queries. Powered by Tavily.

### Intent Routing Table

| Intent | LLM | Route |
|--------|-----|-------|
| `chat` | Groq | Standard response |
| `research_quick` | Groq | Tavily multi-search |
| `research_deep` | Claude | DeepResearch subgraph |
| `plan` | Claude | PlanBuilder node |
| `organize` | Groq | TaskScheduler subgraph |
| `breakdown` | Groq | OverloadBreakdown subgraph |
| `search` | Groq | WebSearch mode |
| `file_question` | Gemini Vision / Whisper | FileProcessor node |

### Multimodal enhancements (Sprint 3 base + Sprint 6 additions)

- Multi-file drop in single message (Sprint 3)
- Cross-file questions: "compare these two documents" (Sprint 6)
- File referenced in plan artifacts: "this plan is based on [filename]" (Sprint 6)

**Acceptance criteria:**
- Quick research: cited answer <30s
- Deep research: structured report cross-referencing user context
- `/search` shows visible source cards with domain + title
- `/plan` saves as real Project with ESL-gated task creation
- `/organize` produces weekly schedule respecting calendar + goal priorities + quiet hours
- `/breakdown` produces topic clusters from all connected sources
- WebSocket: user can cancel mid-generation and confirm agent actions
- Claude used for deep research and planning; Groq for everything else

---

## Sprint 7: Proactive Intelligence (Post-14 weeks)

Powered by the MCP surface built in Sprints 2–6. Scheduled LangGraph background agents:

- **Pre-meeting brief:** 30 min before each calendar event → research attendees + relevant docs + open tasks
- **Inbox digest:** Morning summary of emails + Slack + overnight calendar changes
- **Daily focus plan:** `/organize` run automatically each morning as push notification
- **Deadline warnings:** Task due-date alerts with suggested focus time blocks
- **Related-items clustering:** Surface connections between docs/tasks/emails the user hasn't noticed

**Rules:** Fully user-controlled. Frequency controls, quiet hours, source opt-in, full explanation on every card. Dismiss/snooze/never. All logged in ESL transparency.

---

## MCP Surface — Complete Map (end of Sprint 6)

```
FastAPI routes (Sprint 2a):    All existing /api/* routes
calendar (Sprint 2b):          list_events, create_event, update_event, delete_event, find_free_slots
gmail (Sprint 2b):             list_messages, get_message, send_message, search_messages, create_draft
slack (Sprint 2b):             list_channels, get_messages, send_message, search_messages
documents (Sprint 3):          upload_document, search_documents, get_document_chunk, extract_tasks_from_doc
projects (Sprint 4):           create_project, update_project, list_projects, link_task, link_document
tasks (Sprint 4):              create_task, update_task, confirm_task, list_tasks, extract_tasks_from_source
context (Sprint 5):            update_memory_block, correct_assumption, get_context_explanation
research-tools (Sprint 6):     deep_research, web_search, plan_builder, file_processor
```

---

## Technical Stack (Revised)

| Layer | Current | Revised |
|-------|---------|---------|
| Agent framework | LangChain agents | **LangGraph StateGraph** |
| Tool integration | Hardcoded LangChain tools | **FastAPI-MCP + Skills registry (YAML)** |
| Connector pattern | Custom BaseConnector ABC | **MCP namespaces (in-process via FastAPI-MCP)** |
| Observability | ESL audit log only | **Langfuse + ESL audit log (correlated)** |
| Streaming | SSE only | **SSE (default) + WebSocket (interactive, Sprint 6)** |
| Auth/session | localStorage JWT | **HttpOnly cookie + localStorage display cache** |
| Memory | M1 PostgreSQL + M2 Weaviate | **+ Letta-style core/archival memory blocks** |
| RAG | Hybrid search | **+ Cross-encoder reranker (top-50 → top-10)** |
| Multimodal | Text only | **+ Gemini Vision + Whisper audio** |
| LLM routing | Groq only | **Groq (chat/search) + Claude (research/planning)** |

**New dependencies to add to `requirements.txt`:**
- `fastapi-mcp>=0.4.0`
- `langfuse>=2.0.0`
- `langgraph>=0.2.0`
- `cohere>=4.0.0` (reranker, OR `sentence-transformers>=2.2.0` for self-hosted)
- `anthropic>=0.25.0` (Claude for deep research/planning)
- `openai-whisper` (audio transcription, OR use Groq's Whisper endpoint)

---

## ESL Integrity — All Features Covered

| Feature | ESL action type | Sprint added |
|---------|----------------|-------------|
| Slack send | `SLACK_SEND` *(added to `ActionType` in Sprint 2a Workstream B)* | 2a |
| Gmail send | `EMAIL_SEND` | existing |
| Calendar write | `CALENDAR_WRITE` | existing |
| Settings update | `DATA_COLLECTION` (existing ESL gate maintained) | existing |
| User status change | No ESL gate — user directly controls their own mode state | 2a |
| Deep research | `CONTENT_GENERATION` — topic filter applied to queries | 6 |
| Web search | `CONTENT_GENERATION` — topic filter applied to queries | 6 |
| File insertion (ingestion) | `DATA_COLLECTION` — sensitivity check before ingestion | 3 |
| File question (LLM response) | `CONTENT_GENERATION` — topic filter on AI response content | 3 |
| Plan creation (task write) | `DATA_COLLECTION` | 4 |
| Plan creation (calendar block) | `CALENDAR_WRITE` | 4 |
| Task scheduling | `CALENDAR_WRITE` — quiet hours + focus mode enforced | 4 |
| Memory block update | `DATA_COLLECTION` | 5 |
| Information Overload Breakdown | `CONTENT_GENERATION` — topic filter applied before LLM | 5 |
| Proactive briefs | `PROACTIVE_SUMMARY` — frequency + quiet hours enforced | 7 |

*(All `ActionType` enum values use UPPER_SNAKE_CASE in Python; lowercase `snake_case` string values are used in Skills YAML and audit logs.)*

---

## Design Constraints (Carried Forward)

- No fully autonomous write actions. Confirmation required for all external mutations.
- No dark patterns. No engagement optimization. No FOMO, urgency inflation, or infinite scroll.
- ESL is structurally enforced (LangGraph node), not conventionally enforced (function call).
- Every proactive suggestion has a visible "why" traceable to the user's context.
- User can always correct assumptions, dismiss suggestions, and view the full audit trail.
- Information Overload Breakdown strips manipulation/FOMO language from summaries before display.
