# Ethic Companion

> Trust over engagement. Always.

Ethic Companion is a personal AI assistant built on a single non-negotiable
principle: **every action that affects you is gated by an Ethical Safeguard
Layer (ESL) that enforces the boundaries and values you declared.** Notifications
after your quiet hours? Vetoed. Phrasing that manipulates? Rewritten. Decisions
the assistant made? Logged, every one, where you can read them.

It ingests your calendar, email, Slack, and uploaded documents into a single
context, answers questions with citations to your own sources, and gets out of
your way the rest of the time. No engagement metrics. No FOMO. No dark patterns.

[![CI](https://github.com/CatiaMachado997/RelevanceEthicCompanion/actions/workflows/ci.yml/badge.svg)](https://github.com/CatiaMachado997/RelevanceEthicCompanion/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## Screenshots

<!--
Drop screenshots here when ready. Suggested shots:
  - The chat with a citation card under an answer
  - The Transparency tab showing an ESL decision log
  - The onboarding wizard (3-step setup)
  - The integrations page with the connector status footer
-->

_Screenshots coming soon. For now, the [session summary](docs/sessions/2026-05-20-sprints-f-through-h.md) walks through what's been built and the architecture decisions behind it._

---

## What's in it

| Capability | What it does |
|---|---|
| **Grounded chat (RAG)** | Hybrid search over your documents in Weaviate, optional Jina rerank, citations rendered as cards under each answer. `/ask` slash command forces retrieval. |
| **Connectors** | Gmail, Google Calendar, Slack. Normalized ingestion into `source_items` + `document_chunks`. Backfill, scheduled sync, OAuth lifecycle, per-connector status (indexed / failed / pending). |
| **Agentic orchestrator** | LangGraph multi-step planner with a 3-step cap. ESL gates proactive flows. All tool calls land in a Transparency telemetry table with full retrieval breadcrumbs. |
| **Work management** | Tasks with `blocks` / `blocked_by` dependencies (cycle prevention via recursive CTE). Goal milestones, project rollups, weekly review. |
| **First-run onboarding** | Three-step wizard: connect a source → declare 2-3 values → seed a goal. Skippable per step. Dashboard layout redirect-guards new accounts into it. |
| **Ops safety** | Migrations auto-run on boot (fail-loud). Daily retention prune. System Health views. Worktree env-symlink helper. |

---

## Quick start

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set GROQ_API_KEY, GEMINI_API_KEY, SUPABASE_*, …
docker compose up -d   # Postgres + Weaviate
python main.py         # → http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                        # → http://localhost:3000
```

### Auth

Supabase. Set `ENVIRONMENT=development` in `backend/.env` to bypass auth for local dev.

### Optional: retrieval rerank

Set `JINA_API_KEY` in `backend/.env` to enable Jina's cross-encoder rerank
(free tier: 100 RPM / 100K TPM). Retrieval works fine without it — hybrid
search returns the raw top-K.

---

## Architecture

```
Frontend (Next.js 16, App Router, React Query)
        │
        ▼
Backend (FastAPI, LangGraph)
        │
        ├── Ethical Safeguard Layer  ◀── mandatory gateway for every user-facing action
        │
        ├── Postgres (Supabase)      ◀── users, values, goals, tasks, source_items, telemetry
        └── Weaviate                 ◀── DocumentMemory (hybrid dense + BM25, alpha=0.7)
```

**The ESL is not optional.** It is the gateway every action must pass through.
The architecture is built so you cannot ship a feature that bypasses it.

See [`CLAUDE.md`](CLAUDE.md) for the full operating contract.

---

## Tech stack

- **Backend** — FastAPI, LangGraph (multi-step planner), psycopg, APScheduler, Weaviate v4
- **Frontend** — Next.js 16, TypeScript, Tailwind, Radix UI, React Query
- **Data** — Postgres with pgvector (Supabase), Weaviate for hybrid search
- **LLMs** — Groq (Llama 3.3 70B default, OSS-120B, GPT-OSS-20B), Gemini for embeddings, optional Jina rerank
- **Deploy** — Cloud Run (backend), Vercel (frontend)

---

## Core principles

1. **User well-being is the primary metric.** Not DAU, not time-in-app, not
   message count. If a feature makes the assistant feel more useful but
   nudges the user toward unhealthy patterns, the feature loses.
2. **User control is non-negotiable.** Boundaries declared in `user_values`
   must be enforced. Always. No "just this once" exceptions.
3. **Non-manipulation by design.** No FOMO, no urgency manufacturing, no
   dark patterns. The ESL has a `ManipulationDetector` and an
   `EngagementDetector` for a reason — they say no.
4. **Transparency by default.** Every ESL decision is logged. The
   Transparency tab in the app surfaces every tool call with full input,
   output, and retrieval trace.

---

## Development

```bash
# Backend
cd backend
pytest --tb=short -q
pytest tests/test_esl.py -v    # ESL changes? run this first.
black . && flake8 . && mypy .

# Frontend
cd frontend
npx tsc --noEmit
npm run test
```

**Critical rule:** changes that touch `esl/` or `services/orchestrator/` must
include a passing `tests/test_esl.py` run before commit. The ESL is the
single architectural invariant of this project.

---

## Project structure

```
backend/              FastAPI app, ESL engine, orchestrator, services
  esl/                  Engine, models, rules, audit
  services/             Connectors, RAG retrieval, rerank, document processing
  orchestrator/         LangGraph nodes
  routes/               HTTP API
  migrations/           Numbered SQL migrations, auto-run on boot
  tests/                pytest suite (~440 tests)
frontend/             Next.js 16 App Router
  app/dashboard/        Authenticated UI
  app/onboarding/       First-run wizard
  components/           UI components (chat, transparency, sidebars, …)
  hooks/                useAuth, useOnboardingState, …
docs/
  plans/                Sprint-by-sprint implementation plans
  sessions/             Session summaries — narrative recaps of work shipped
  superpowers/          Design specs and engineering playbook
```

---

## Documentation

- [Session summary — Sprints F, G, H](docs/sessions/2026-05-20-sprints-f-through-h.md) — narrative recap of recent work, including the M-KOPA end-to-end RAG verification
- [Sprint plans](docs/plans/) — one markdown file per sprint, problem → architecture → tasks → verification
- [`CLAUDE.md`](CLAUDE.md) — operating contract for AI agents working on this codebase
- [`SECURITY.md`](SECURITY.md) — responsible disclosure
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to contribute

---

## License

[Apache 2.0](LICENSE)

---

## Author

**Cátia Machado** — *Trust over Engagement. Always.*
