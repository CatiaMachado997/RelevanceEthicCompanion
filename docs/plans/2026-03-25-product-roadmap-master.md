# Ethic Companion — Master Product Roadmap

> **Status note (2026-07-01):** The Pillar/Backlog tables and Sprint Plans
> table below are from this doc's original writing (2026-03-25) and are
> stale — most of Phases 2–4 shipped via a lettered Sprint A–H sequence not
> reflected here (`docs/plans/2026-04-2*-sprint-{b,c,d,e}-*.md` and
> `2026-04-27-sprint-{f,g,h}-*.md`; see `docs/sessions/2026-05-20-sprints-f-through-h.md`
> for a narrative summary of the most recent three). Sprint C's own doc
> states it closes "the final pillar of the original 7-phase master
> roadmap." Corrections are marked inline below; the Phase Breakdown prose
> further down was NOT re-verified against current code and may describe
> designs that shipped differently than planned.
>
> Also not reflected in this doc at all: a Composio-based tool marketplace
> (`services/composio_tools.py`, `services/tool_registry.py`,
> `routes/tool_marketplace.py`) that appears to provide broader third-party
> integrations (including Drive/Notion references) alongside the bespoke
> Gmail/Slack/Calendar connectors this doc describes. Not independently
> verified for scope — worth a dedicated audit before trusting either the
> "P2" backlog below or this note as the full picture.

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

| Pillar | Status (2026-03-25) | Status (2026-07-01) | Description |
|--------|--------|--------|-------------|
| **P1 Identity & User Model** | Partial | Partial — onboarding wizard shipped (Sprint H), still no canonical unified model | Profile, values, goals, preferences, boundaries, memory |
| **P2 Connections & Ingestion** | Scaffolded | Shipped — Gmail/Slack/Calendar end-to-end with normalized `source_items`, sync status UI, reindex (Sprint B, F) | Calendar/Gmail/Slack ingestion + visibility |
| **P3 Knowledge & Documents** | Missing | Shipped — upload/extract/chunk/embed/search/cite, PDF+DOCX (Sprint A, G) | Documents as a product surface |
| **P4 Work Management** | Hints only | Shipped — projects/tasks model, rollups, weekly review (Sprint D) | Tasks, projects, extraction |
| **P5 Agentic Workspace** | Fragmented | Shipped — unified per Sprint C ("final pillar of the original 7-phase roadmap") | Chat + tools + search |
| **P6 Trust & Governance** | Strong | Strong — unchanged | ESL, transparency, value alignment |

---

## Priority Backlog

> **2026-07-01 pass:** checkboxes below updated against the session summary
> and sprint plan headers only (not a line-by-line code audit — verify
> before relying on an unchecked item still being open).

### P0 — Do Now
- [x] Add health checks (DB, Weaviate, scheduler, OAuth) — `services/system_health.py`, `routes/status.py`
- [x] Wire feedback buttons in chat → feedback API end-to-end
- [x] Validate Google Calendar sync end-to-end
- [x] Define normalized `source_items` schema
- [x] Fix error/loading/empty states on dashboard + integrations (Sprint F error-noise sweep)
- [ ] Unify architecture docs (remove Firebase references, standardize Supabase)
- [ ] Stabilize Docker/local runtime (Weaviate-tolerant startup) — CI now has real service containers as of 2026-07-01; local Docker-tolerance not re-verified
- [ ] Validate transparency logs from real ESL decisions — Transparency tab + retrieval breadcrumbs shipped (Sprint G); "validated against real decisions" not independently re-confirmed

### P1 — Next Release
- [x] Gmail integration end-to-end (Sprint B)
- [x] Slack integration end-to-end (Sprint B)
- [x] Documents domain: upload / extract / chunk / embed / search (Sprint A, G — PDF/DOCX)
- [x] Search expanded to docs + source items
- [x] Projects model + API (Sprint D)
- [x] Tasks model, extraction, confirmation workflow (Sprint D)
- [ ] Connector framework refactor (`DataIngestionService` → interface-based) — connectors work end-to-end; not confirmed whether the interface refactor itself landed or just the integrations
- [ ] `user_context_snapshot` service — Phase 5 concept below; not confirmed shipped

### P2 — After That
- [ ] Google Drive / Docs ingestion — Composio tool marketplace has Drive/Notion references (`services/composio_tools.py`); scope not verified
- [ ] Better proactive insights (pre-meeting brief, digest, daily plan) — Today feed shipped (Sprint F) is adjacent but not the same as proactive push insights
- [ ] Cross-source entity linking (person/topic graphs)
- [ ] Richer transparency UX (why this was shown) — retrieval breadcrumbs shipped (Sprint G); may partially cover this
- [ ] Work planning workflows
- [ ] Mobile polish
- [ ] Audio modality
- [ ] Rerank eval harness (recall@5) — deferred from Sprint G
- [ ] Per-project document scoping in chat — deferred from Sprint G, needs project-picker UI
- [ ] Scheduler observability (`scheduled_job_runs` table + System Health row + alerting) — deferred from Sprint G/H, called "the natural fourth ops-safety sprint"
- [ ] OAuth `return_to` support for onboarding (currently uses a localStorage workaround) — deferred from Sprint H, ~2 files
- [ ] OCR for image-only PDFs — accepted gap, pypdf returns empty + warns

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

> This table (Sprint 1–4) was superseded by a lettered Sprint A–H sequence
> that actually shipped Phases 2–6. The Sprint 1–4 files below may still be
> useful as historical Phase 0/1 planning, but the real execution history
> is the A–H list.

| Sprint | Plan File | Status (2026-03-25) |
|--------|-----------|--------|
| Sprint 1: Stabilization | `2026-03-25-sprint-1-stabilization.md` | Ready |
| Sprint 2: Connector framework + Gmail/Slack | TBD | Not written |
| Sprint 3: Documents domain | TBD | Not written |
| Sprint 4: Projects/Tasks domain | TBD | Not written |

### Actual execution history (Sprint A–H, shipped)

| Sprint | Plan File | Covers |
|--------|-----------|--------|
| A: RAG/citations + Documents | not located under this name; see Sprint B's predecessor note | Documents domain (P3) |
| B: Connector framework + Gmail/Slack | `2026-04-25-sprint-b-connector-framework.md` | P2 |
| D: Work Management Depth | `2026-04-26-sprint-d-work-management-depth.md` | P4 (ran before C, by request) |
| C: Agentic Workspace Unification | `2026-04-27-sprint-c-agentic-workspace-unification.md` | P5 — closes the original 7-phase roadmap |
| E: Polish & Ops | `2026-04-27-sprint-e-polish-and-ops.md` | Post-roadmap hardening |
| F: Daily-use polish | `2026-04-27-sprint-f-daily-use-polish.md` | Index-failure visibility, Today feed, blank-chat/memory bugs |
| G: Retrieval depth + ops safety | `2026-04-27-sprint-g-retrieval-depth-ops-safety.md` | Auto-migrations, PDF/DOCX, rerank, retrieval breadcrumbs |
| H: First-run onboarding | `2026-04-27-sprint-h-onboarding.md` | Onboarding wizard, redirect guard |

Narrative summary of F–H: `docs/sessions/2026-05-20-sprints-f-through-h.md`.
