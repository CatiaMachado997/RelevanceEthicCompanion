# Ethic Companion — Master Product Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve Ethic Companion from a relevance engine into a personal work orchestration layer — ingesting documents and communications, building a reliable 360° user context, reasoning over priorities and constraints, and helping the user manage work end-to-end through chat, search, summaries, tasks, and proactive nudges.

**Architecture:** FastAPI (Python) backend + Next.js 15 frontend + PostgreSQL (M1 structured) + Weaviate (M2 semantic) + Supabase Auth. The ESL (Ethical Safeguard Layer) is a mandatory gateway for all user-facing actions and must remain first-class throughout all phases.

**Tech Stack:** FastAPI · Groq/LLMs · LangChain tools · Weaviate · PostgreSQL/pgvector · Supabase Auth · Next.js 15 · Tailwind CSS v4 · Radix UI

---

## North Star User Flow

> A user signs in → connects apps → uploads docs → defines values/goals → asks "what should I focus on today?" → sees a response grounded in meetings/emails/docs/tasks → turns that response into tasks → receives a useful pre-meeting brief.

Every feature should support this flow.

---

## Six Product Pillars

| Pillar | Status | Description |
|--------|--------|-------------|
| **P1 Identity & User Model** | Partial | Profile, values, goals, preferences, boundaries, memory — needs a canonical unified model |
| **P2 Connections & Ingestion** | Scaffolded | Calendar/Gmail/Slack exist, missing normalized pipeline + UI visibility |
| **P3 Knowledge & Documents** | Missing | Upload, chunk, embed, search, cite docs — not yet a product surface |
| **P4 Work Management** | Hints only | Tasks, projects, extraction — need to become a full product area |
| **P5 Agentic Workspace** | Fragmented | Chat + tools + search exist but are not unified |
| **P6 Trust & Governance** | Strong | ESL, transparency, value alignment — keep first-class in all phases |

---

## Priority Backlog

### P0 — Do Now
- [ ] Unify architecture docs (remove Firebase references, standardize Supabase)
- [ ] Stabilize Docker/local runtime (Weaviate-tolerant startup)
- [ ] Add health checks (DB, Weaviate, scheduler, OAuth)
- [ ] Wire feedback buttons in chat → feedback API end-to-end
- [ ] Validate transparency logs from real ESL decisions
- [ ] Validate Google Calendar sync end-to-end
- [ ] Define normalized `source_items` schema
- [ ] Fix error/loading/empty states on dashboard + integrations

### P1 — Next Release
- [ ] Connector framework refactor (`DataIngestionService` → interface-based)
- [ ] Gmail integration end-to-end
- [ ] Slack integration end-to-end
- [ ] Documents domain: upload / extract / chunk / embed / search
- [ ] Search expanded to docs + source items
- [ ] Projects model + API
- [ ] Tasks model, extraction, confirmation workflow
- [ ] `user_context_snapshot` service

### P2 — After That
- [ ] Google Drive / Docs ingestion
- [ ] Better proactive insights (pre-meeting brief, digest, daily plan)
- [ ] Cross-source entity linking (person/topic graphs)
- [ ] Richer transparency UX (why this was shown)
- [ ] Work planning workflows
- [ ] Mobile polish
- [ ] Audio modality

---

## Phase Breakdown

### Phase 0: Product Reset & Architecture Alignment
**Goal:** Make the repo reflect the actual product direction.

- Replace stale README + roadmap
- Canonical product statement: "personal relevance + work orchestration assistant"
- Remove auth split-brain (Firebase refs → Supabase only)
- Define canonical domain entities:
  `UserProfile, UserValue, Goal, Project, Connection, SourceItem, Document, Conversation, Task, Insight, FeedbackEvent, TransparencyLog`

**Acceptance:** One architecture doc, one auth strategy, one normalized data model.

---

### Phase 1: Stabilize Current MVP Spine
**Goal:** Make the current app reliably usable. *(See Sprint 1 detailed plan.)*

**Workstream A — Infrastructure**
- docker-compose: Postgres + Weaviate only, tolerant startup
- Health checks for DB, Weaviate, scheduler, OAuth config
- Seed data / dev fixtures

**Workstream B — Feature Hardening**
- auth → dashboard → integrations → sync → chat end-to-end
- Feedback, transparency, values/goals/settings all persist + reload
- Error/loading/empty states correct

**Workstream C — Context Reliability**
- `ContextManager` is single entry point
- Merges M1 (values, goals, profile, events, feedback) + M2 (conversation/event embeddings)
- Graceful fallback when Weaviate unavailable

**Acceptance:** Signed-in user can connect Calendar, sync, ask context-aware questions, submit feedback. App degrades gracefully. No mock-only routes.

---

### Phase 2: Unified Connections Layer
**Goal:** Move from "some integrations" to a proper integrations platform.

**Normalized source item schema** — every source maps to:
```
source_type, source_item_type, external_id, title, body,
metadata, timestamps, project_links, person_links, topic_links,
embedding_status, sensitivity_flags, relevance_hints
```

**Backend:** Refactor to connector interface: `authorize() / refresh_tokens() / incremental_sync() / normalize_item() / store_item() / index_item()`

New tables: `source_items`, `ingestion_job_history`, `sync_errors`, `connection_health`

**Frontend:** Integrations page shows connected/disconnected, last sync, item counts, health status, permissions, disconnect/resync/repair.

**Priority:** Calendar → Gmail → Slack → Upload → Drive → Notion

**Acceptance:** Every source has visible sync status. New items normalized and indexed. User can see what the app knows per source.

---

### Phase 3: Documents as First-Class Product
**Goal:** Knowledge work, not just calendar/chat.

**Scope v1:** Upload → extract text → chunk → embed → store → search → Q&A → citations

**New models:** `documents`, `document_chunks`, `document_links`, `project_documents`

**New UI:** Documents page, upload flow, document detail, "chat with doc", "add to project"

**Assistant:** Query across all docs / selected docs / compare / summarize / extract action items

**Acceptance:** Upload PDF → immediately ask questions → answers reference chunks → docs attach to projects.

---

### Phase 4: Projects & Task Management
**Goal:** Move from relevance assistant to work manager.

**Hierarchy:** Goals (intentions) → Projects (containers) → Tasks (actionable units)

**Task fields:** title, description, status, priority, due_date, source_origin, project_id, doc_links, message_links, ai_confidence, user_confirmed

**Entry paths:** manual / assistant suggestion / doc extraction / email+Slack extraction / calendar extraction

**New UI:** Projects page, Tasks page, Today view, Task detail drawer, source traceability, AI-task confirmation workflow

**Acceptance:** Users manage projects/tasks in app. AI suggests tasks, requires confirmation for writes. Tasks link to source material. Dashboard shows active work.

---

### Phase 5: 360° User Context Layer
**Goal:** Make personalization and proactive help materially better.

**`user_context_snapshot` service** — computed on: after sync / after conversation / after feedback / after task changes / before proactive suggestions

**Snapshot sections:** `focus_now`, `active_projects`, `urgent_items`, `recent_decisions`, `unresolved_threads`, `calendar_pressure`, `communication_pressure`, `values_and_boundaries`, `recommended_next_actions`

**UI:** "Your context" panel on dashboard, "why I think this matters" explanations, ability to correct assumptions.

**Acceptance:** App explains its current understanding. User can correct it. Proactive suggestions draw from this context.

---

### Phase 6: Chat as True Workspace Assistant
**Goal:** Chat becomes the orchestration surface for everything.

**Capabilities:** Attachments, conversation-scoped context packs, choose active sources per thread, streamed answers with citations, artifact-aware outputs (summaries/task lists/plans/drafts), follow-up actions (save as note / create tasks / pin insight / link to project)

**Behind the scenes:** Intent classification → route to appropriate sources → transparent tool traces → ESL checks before any action

**Acceptance:** Chat is the main command center. Tool use visible. Answers become structured objects. System feels stateful and context-aware.

---

### Phase 7: Proactive Intelligence
**Goal:** Deliver the relevance engine promise. (Only after Phases 3–5 complete.)

**Features v1:** Pre-meeting brief, inbox digest, daily focus plan, project status snapshot, deadline warnings, related-items clustering

**Rules:** Fully user-controlled, frequency controls, quiet hours, source opt-in, full explanation, dismiss/snooze/never, logged in transparency.

**Acceptance:** Proactive cards are useful, not spammy. Respect values/quiet times. Every suggestion has a visible "why."

---

## 12-Week Schedule

| Weeks | Focus |
|-------|-------|
| 1–2 | Phase 0+1: Stabilization, auth cleanup, MVP hardening |
| 3–4 | Phase 2: Connector framework, Calendar/Gmail/Slack end-to-end |
| 5–6 | Phase 3: Documents upload/index/search/Q&A |
| 7–8 | Phase 4: Projects + tasks + AI extraction + today view |
| 9–10 | Phase 5: Context snapshots + richer dashboard + explainability |
| 11–12 | Phase 6+7: Chat as workspace + proactive cards + polish |

---

## Design Constraints

> **Do not** make write actions fully autonomous yet. Read-heavy and suggest-heavy is correct for now. Require confirmation for destructive/external actions.

> **Do not** model everything as chat memory. Introduce durable structured objects early: project, task, document, source item, insight.

> **Do not** let integrations remain OAuth cards. They need sync observability, item visibility, and searchability.

> **Do not** bury ESL. Make it part of the visible product story on every recommendation and proactive suggestion.

---

## Sprint Plans (separate documents)

| Sprint | Plan File | Status |
|--------|-----------|--------|
| Sprint 1: Stabilization | `2026-03-25-sprint-1-stabilization.md` | Ready |
| Sprint 2: Connector framework + Gmail/Slack | TBD | Not written |
| Sprint 3: Documents domain | TBD | Not written |
| Sprint 4: Projects/Tasks domain | TBD | Not written |
