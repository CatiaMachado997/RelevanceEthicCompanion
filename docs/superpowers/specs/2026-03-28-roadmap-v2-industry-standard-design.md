# Ethic Companion — Revised Roadmap V2: Industry-Standard Foundation
**Spec Date:** 2026-03-28
**Status:** Approved
**Author:** Brainstorming session with user

---

## Overview

This document revises the master product roadmap to incorporate industry-standard tooling (MCP, LangGraph, Langfuse, Skills registry, WebSocket) and expands the Chat as Workspace phase with five major new features: deep research mode, multimodal file insertion, explicit web search, full plan-in-chat workspace, and task scheduling intelligence.

**Core philosophy unchanged:** Trust over Engagement. ESL remains a mandatory gateway for all user-facing actions throughout every phase.

---

## Problem Statement

The existing roadmap (v1) had three structural gaps:

1. **Custom connector framework** — Sprint 2 planned to build a proprietary `authorize/sync/normalize` adapter interface. This would become technical debt as MCP (now industry standard with 97M+ monthly downloads) matures. Every connector would need rebuilding later.

2. **Bypassable ESL** — The current `orchestrator_v2.py` calls `evaluate_action()` as a function. Nothing structurally prevents a future developer from skipping it. The ESL must be architecturally enforced, not conventionally enforced.

3. **No observability** — A trust-first product has no LLM tracing, token cost monitoring, or tool success tracking. It is impossible to prove the system is behaving correctly without this.

---

## Approach: Foundation Sprint + MCP-Native Connectors

Insert **Sprint 2a (Foundation, 2 weeks)** before the connector work. This sprint rewrites the orchestrator in LangGraph, wraps all FastAPI routes as MCP tools, adds Langfuse observability, and establishes a skills registry. Every phase after 2a builds MCP-native — connectors as MCP servers, documents as MCP resources, tasks as MCP resources, tools as YAML-described skills.

**Result:** By Sprint 6, the orchestrator discovers and calls everything through MCP. Adding a new tool = one YAML file. No orchestrator code changes.

---

## Revised Phase Map

| Sprint | Weeks | Focus | Status |
|--------|-------|-------|--------|
| Sprint 1 | 1–2 | Stabilization | In progress |
| **Sprint 2a** | 3–4 | **Foundation** | New |
| Sprint 2b | 5–6 | Connections as MCP servers | Replaces old Sprint 2 |
| Sprint 3 | 7–8 | Documents | Updated |
| Sprint 4 | 9–10 | Projects & Tasks | Updated |
| Sprint 5 | 11–12 | 360° Context Layer | Updated |
| Sprint 6 | 13–14 | Chat as Workspace | Heavily expanded |
| Sprint 7 | 15+ | Proactive Intelligence | Post-MVP |

---

## Sprint 2a: Foundation (New — Weeks 3–4)

**Goal:** Replace the ad-hoc orchestrator with a clean, observable, MCP-native foundation. No user-visible features. Everything downstream depends on this.

### Deliverable 1 — LangGraph Orchestrator (full rewrite)

`backend/services/orchestrator_v2.py` (914 lines) is replaced by `backend/orchestrator/graph.py`.

**Graph structure:**
```
UserInput
  → ContextBuilder          # Assembles M1 + M2 context
  → IntentClassifier        # Routes: chat / research / plan / search / file
  → ToolPlanner             # Decides which MCP tools to call
  → ToolExecution (loop)    # Executes tools, max 5 rounds
  → ESLGateway              # MANDATORY node — every path passes through ESL
      ↓ APPROVED
  → ResponseFormatter       # Structures output (text / artifact / card)
      ↓ VETOED
  → ExplainVeto             # Returns ESL reason to user
      ↓ MODIFIED
  → ApplyModification → ResponseFormatter
  → Output (SSE / WebSocket stream)
```

**Key properties:**
- ESL is a graph node, not a function call — structurally impossible to bypass
- Typed `AgentState` dataclass carries context, decision, tool results through every node
- Conversation history and semantic memory stored after every graph run
- Token budget tracked as state; warnings emitted at 75% and 85%

**File layout:**
```
backend/orchestrator/
  graph.py          # StateGraph definition
  nodes/
    context.py      # ContextBuilder node
    intent.py       # IntentClassifier node
    tools.py        # ToolPlanner + ToolExecution nodes
    esl.py          # ESLGateway node (wraps existing esl/engine.py)
    response.py     # ResponseFormatter node
  state.py          # AgentState typed dict
  subgraphs/
    deep_research.py  # DeepResearch subgraph (Phase 6)
    task_scheduler.py # TaskScheduler subgraph (Phase 6)
```

### Deliverable 2 — FastAPI-MCP Server

```python
# backend/main.py — single addition
from fastapi_mcp import FastApiMCP
mcp = FastApiMCP(app)
mcp.mount()
```

All existing FastAPI routes become discoverable MCP tools automatically. The orchestrator's ToolPlanner calls `list_tools()` at startup and `call_tool()` at runtime — no hardcoded tool lists.

**MCP surface after Sprint 2a:**
- All existing `/api/*` routes exposed as MCP tools
- Tool descriptions auto-generated from OpenAPI schemas

### Deliverable 3 — Skills Registry

```
backend/skills/
  web_search.yaml
  query_memory.yaml
  query_calendar.yaml
  get_user_goals.yaml
  create_note.yaml
```

Each YAML describes: name, description, mcp_tool, parameters, esl_action_type, requires_confirmation. The ToolPlanner loads skills at startup. Adding a new capability = new YAML file, zero orchestrator changes.

### Deliverable 4 — Langfuse Observability

Langfuse SDK wraps every:
- LLM call (model, tokens, latency, cost)
- Tool execution (tool name, success/fail, duration)
- ESL decision (status, reason, confidence, violated values)

ESL audit log entries are correlated with Langfuse trace IDs — full decision lineage visible in one place. Open-source, self-hosted option available.

### Deliverable 5 — WebSocket Transport

WebSocket endpoint added alongside existing SSE at `/api/chat/ws`.

| Transport | Use case |
|-----------|----------|
| SSE | Simple token streaming (existing chat) |
| WebSocket | Cancel mid-generation; human-in-the-loop approval; real-time tool status; multi-device sync |

Frontend chat page supports both — SSE by default, WebSocket when agent actions require user confirmation.

**Acceptance criteria (Sprint 2a):**
- Existing chat smoke test passes against new LangGraph orchestrator
- ESL decisions appear in both audit log and Langfuse traces
- All existing API routes discoverable via MCP `list_tools()`
- New skill added via YAML without touching `graph.py`
- WebSocket chat works end-to-end

---

## Sprint 2b: Connections as MCP Servers (Weeks 5–6)

**Goal:** Build Calendar, Gmail, Slack as MCP servers — not custom adapters.

Each connector is an independent MCP server with standard tools:

```
calendar-mcp-server/
  tools: list_events, create_event, update_event, delete_event, find_free_slots
  resources: calendar://events/{date_range}

gmail-mcp-server/
  tools: list_messages, get_message, send_message, search_messages, create_draft
  resources: gmail://inbox, gmail://thread/{id}

slack-mcp-server/
  tools: list_channels, get_messages, send_message, search_messages
  resources: slack://channel/{id}
```

**Normalized ingestion:** Every connector writes to `source_items` table via a shared `IngestionService`. Item schema: `source_type, external_id, title, body, metadata, embedding_status, sensitivity_flags`.

**Sync observability UI:** Integrations page shows connection status, last sync time, item counts, health, disconnect/resync controls.

**ESL integration:** Calendar writes and message sends are `action_type=CALENDAR_WRITE` and `action_type=EMAIL_SEND` — ESL-gated before any external mutation.

**Acceptance criteria:**
- Calendar sync fetches events, normalizes to source_items, indexes in Weaviate
- Gmail sync fetches last 7 days of inbox, normalized + indexed
- Slack sync fetches recent messages from connected channels
- User can see sync health per connector in UI
- No connector bypasses ESL for write operations

---

## Sprint 3: Documents (Weeks 7–8)

**Goal:** Documents as a first-class product surface. Upload → process → search → Q&A → cite.

**Ingestion pipeline:**
```
Upload → ExtractText (pypdf / python-docx) → Chunk (512 tokens, 20% overlap)
  → Embed (Google Gemini) → Store chunks in Weaviate
  → ESL sensitivity check → Index in PostgreSQL (documents + document_chunks)
```

**Retrieval (upgraded RAG):**
```
Query → Dense vector search + BM25 sparse search (hybrid)
  → Retrieve top-50 candidates
  → Rerank (cross-encoder, top-10)
  → Feed to LLM with citations
```

**MCP surface:**
```
documents-mcp-server/
  tools: upload_document, search_documents, get_document_chunk, extract_tasks_from_doc
  resources: documents://library, documents://doc/{id}
```

**File insertion in chat (multimodal):**
- Drag-and-drop or paperclip icon in chat input
- Supported: PDF, DOCX, TXT (extracted + chunked), PNG/JPG/WEBP (vision analysis), MP3/WAV (Whisper transcription)
- File processed inline for conversation AND ingested into Documents library
- ESL sensitivity check before ingestion
- AI can immediately answer questions, extract tasks, summarize, or link to project

**Acceptance criteria:**
- Upload PDF → ask questions → answers cite specific chunks
- Image dropped in chat → AI describes and can extract text
- Audio dropped in chat → transcribed via Whisper → AI responds to content
- All ingested files appear in Documents library, searchable

---

## Sprint 4: Projects & Tasks (Weeks 9–10)

**Goal:** Full work management surface. Goals → Projects → Tasks hierarchy.

**Data model:**
```
Goals (intentions, user-defined)
  └── Projects (containers with deadline + status)
        └── Tasks (actionable units with priority, due_date, source_origin, ai_confidence)
```

**Task entry paths:** manual / AI suggestion from chat / document extraction / email+Slack extraction / calendar extraction

**Task confirmation workflow:** AI-suggested tasks require explicit user confirmation before write. ESL gates all task creation and project updates.

**MCP surface:**
```
projects-mcp-server/
  tools: create_project, update_project, list_projects, link_task, link_document
  resources: projects://active, projects://project/{id}

tasks-mcp-server/
  tools: create_task, update_task, confirm_task, list_tasks, extract_tasks_from_source
  resources: tasks://today, tasks://overdue, tasks://by_project/{id}
```

**Make Plans in Chat (full inline workspace):**
- Triggered by `/plan` command or intent detection
- AI produces a **Plan artifact**: milestones, tasks, dependencies as an interactive card
- "Save as Project" → auto-creates Project + all Tasks in app
- Tasks linked to active Goals by alignment score (ESL-weighted)
- Calendar blocks suggested for focus time (user confirms, never auto-written)
- AI stays in conversation context — "move milestone 2 to next week" updates the plan inline
- ESL checks every calendar write and task creation

**Task Scheduling Intelligence:**
- Triggered by `/organize` command or "organize my tasks" in chat
- LangGraph subgraph:
  1. Read all open tasks (priority + due dates)
  2. Read calendar for next 7 days (free blocks via calendar-mcp-server)
  3. Read active goals with priority weights
  4. Produce ranked daily schedule: tasks sorted by `goal_alignment × urgency × available_time`
  5. Render as **Weekly Plan artifact** — draggable, confirm to lock calendar blocks
  6. ESL checks quiet hours and focus mode before any calendar write

**Acceptance criteria:**
- User creates project in chat with `/plan` → tasks appear in Tasks view
- `/organize` produces a weekly schedule respecting calendar + goal priorities
- Task extracted from email appears with `ai_confidence` score and confirmation prompt
- All task/project writes gated by ESL

---

## Sprint 5: 360° Context Layer (Weeks 11–12)

**Goal:** Make the app's understanding of the user explicit, correctable, and trustworthy.

**Letta-style memory upgrade:**
```
Core memory blocks (always injected into prompt):
  - persona_block: user's role, working style, communication preferences
  - goals_block: current top 3 goals with priorities
  - boundaries_block: active values and quiet hours
  - focus_block: current focus mode state

Archival memory (semantic retrieval on demand):
  - Past conversations (Weaviate, existing)
  - Processed documents (Sprint 3)
  - Extracted insights and decisions
```

Agents can explicitly write/update memory blocks — memory improves over time rather than degrading.

**`user_context_snapshot` service:** Computed after every sync, conversation, feedback event, or task change. Sections: `focus_now`, `active_projects`, `urgent_items`, `recent_decisions`, `calendar_pressure`, `values_and_boundaries`, `recommended_next_actions`.

**MCP surface:**
```
context-mcp-server/
  resources: context://snapshot, context://memory/core, context://memory/archival
  tools: update_memory_block, correct_assumption, get_context_explanation
```

**UI:** "Your context" panel on dashboard. "Why I think this matters" explanations on every proactive suggestion. User can correct assumptions inline.

**Acceptance criteria:**
- Context snapshot updates after each conversation
- User can view and correct any memory block from the UI
- Every proactive suggestion shows its context source

---

## Sprint 6: Chat as Workspace (Weeks 13–14)

**Goal:** Chat becomes the primary command center for everything in the app.

### Deep Research Mode

**Quick mode (default):** 3–5 parallel Tavily searches, synthesized with citations, ~30 seconds.

**Deep mode (toggle):** Dedicated LangGraph subgraph:
```
DeepResearch subgraph:
  PlanQueries → [Parallel Search × N] → ReadSources → EvaluateCoverage
    → GapDetected? → RefineQueries → [loop, max 3 iterations]
    → CrossReference (user's docs + calendar + goals via MCP)
    → ProduceReport (structured artifact: sections + inline citations)
```

Output: **Research Report artifact** — collapsible sections, inline citations, "Save to Documents" button, "Extract Tasks" button.

### Web Search (explicit first-class mode)

`/search` command or search icon activates visible search mode. User sees:
- Which queries are being run
- Which sources were retrieved (with domain + title)
- Final synthesized answer with clickable source cards

Powered by Tavily. Source cards rendered inline in chat bubble. ESL checks search queries against topic filters.

### Multimodal File Input

Covered in Sprint 3. Sprint 6 adds:
- Multi-file drop in a single message
- Cross-file questions ("compare these two documents")
- File referenced in plan artifacts ("this plan is based on [filename]")

### Intent Routing

IntentClassifier node routes chat input to the right subgraph:

| Intent | Route |
|--------|-------|
| `chat` | Standard conversational response |
| `research_quick` | Tavily multi-search |
| `research_deep` | DeepResearch subgraph |
| `plan` | PlanBuilder subgraph |
| `organize` | TaskScheduler subgraph |
| `search` | WebSearch mode |
| `file_question` | FileProcessor node |

**Acceptance criteria:**
- Quick research returns cited answer in <30s
- Deep research produces structured report with cross-referenced user context
- `/search` shows visible source cards
- `/plan` produces editable artifact that saves as real Project
- `/organize` produces weekly schedule respecting calendar + goal priorities
- Multimodal: PDF, image, audio all processed correctly

---

## Sprint 7: Proactive Intelligence (Post-14 weeks)

Powered entirely by the MCP surface built in Sprints 2–6. Scheduled LangGraph background agents fire on cron schedule:

- **Pre-meeting brief:** 30 min before each calendar event → research attendees + relevant docs + open tasks
- **Inbox digest:** Morning summary of emails + Slack threads + overnight calendar changes
- **Daily focus plan:** `/organize` run automatically each morning, delivered as push notification
- **Deadline warnings:** Task due-date proximity alerts with suggested focus time blocks
- **Related-items clustering:** Surface connections between docs/tasks/emails the user hasn't noticed

**Rules:** Fully user-controlled. Frequency controls, quiet hours, source opt-in, full explanation on every card. Dismiss/snooze/never. All logged in ESL transparency.

---

## MCP Surface — Complete Map (end of Sprint 6)

```
FastAPI routes (Sprint 2a):   All existing /api/* routes
calendar-mcp-server (2b):     list_events, create_event, find_free_slots
gmail-mcp-server (2b):        list_messages, send_message, search_messages
slack-mcp-server (2b):        list_channels, send_message, search_messages
documents-mcp-server (3):     upload_document, search_documents, extract_tasks
projects-mcp-server (4):      create_project, update_project, list_projects
tasks-mcp-server (4):         create_task, confirm_task, list_tasks, extract_tasks
context-mcp-server (5):       snapshot, memory blocks, correct_assumption
research-tools (6):           deep_research, web_search, plan_builder, file_processor
```

---

## Technical Stack (Revised)

| Layer | Current | Revised |
|-------|---------|---------|
| Agent framework | LangChain agents | **LangGraph StateGraph** |
| Tool integration | Hardcoded LangChain tools | **FastAPI-MCP + Skills registry (YAML)** |
| Connector pattern | Custom adapter interface | **MCP servers per connector** |
| Observability | ESL audit log only | **Langfuse + ESL audit log (correlated)** |
| Streaming | SSE only | **SSE (simple) + WebSocket (interactive)** |
| Memory | M1 PostgreSQL + M2 Weaviate | **+ Letta-style core/archival blocks** |
| RAG | Hybrid search (existing) | **+ Cross-encoder reranker (top-50 → top-10)** |
| Multimodal | Text only | **+ Vision (GPT-4V / Gemini) + Audio (Whisper)** |
| LLM provider | Groq (Llama) | **Groq (primary) + Anthropic Claude (research/planning)** |

---

## ESL Integrity — Unchanged and Strengthened

Every new feature preserves ESL as mandatory:

| Feature | ESL action type |
|---------|----------------|
| Deep research | `content_generation` — topic filter applied to queries |
| Web search | `content_generation` — topic filter applied |
| File insertion | `data_collection` — sensitivity check before ingestion |
| Plan creation | `calendar_write` + `data_collection` for each task/event |
| Task scheduling | `calendar_write` — quiet hours + focus mode enforced |
| Proactive briefs | `proactive_summary` — frequency + quiet hours enforced |
| MCP tool calls | Inherit `esl_action_type` from skills YAML |

---

## Design Constraints (Carried Forward)

- No fully autonomous write actions. Read-heavy, suggest-heavy. Confirmation required for all external mutations.
- No dark patterns. No engagement optimization. No FOMO, urgency inflation, or infinite scroll.
- ESL is structurally enforced (LangGraph node), not conventionally enforced (function call).
- Every proactive suggestion has a visible "why" traceable to the user's context.
- User can always correct assumptions, dismiss suggestions, and view the full audit trail.
