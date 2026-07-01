# Ethic Companion

> Trust over engagement. Always.

Ethic Companion is a personal AI assistant built on a single non-negotiable
principle: **every action that affects you is gated by an Ethical Safeguard
Layer (ESL) that enforces the boundaries and values you declared.** Notifications
after your quiet hours? Vetoed. Phrasing that manipulates? Rewritten. Decisions
the assistant made? Logged, every one, where you can read them.

It ingests your calendar, email, Slack, GitHub, Notion, and uploaded documents
into a single context, answers questions with citations to your own sources, and
gets out of your way the rest of the time. No engagement metrics. No FOMO. No dark patterns.

[![CI](https://github.com/CatiaMachado997/RelevanceEthicCompanion/actions/workflows/ci.yml/badge.svg)](https://github.com/CatiaMachado997/RelevanceEthicCompanion/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**Live app:** see deployment section below

---

## What's in it

| Capability | What it does |
|---|---|
| **Grounded chat (RAG)** | Hybrid search over your documents in Weaviate, optional Jina rerank, citations rendered as cards under each answer. `/ask` slash command forces retrieval. |
| **Integrations via Composio** | Gmail, Google Calendar, Slack, GitHub, Notion. One-click OAuth — Composio manages tokens and refresh. Data syncs into the vector store for ESL context; LLM can act on your behalf (draft email, create event, post message). |
| **Agentic orchestrator** | LangGraph multi-step planner with ESL gate on every tool call. Full tool call telemetry in the Transparency tab. |
| **Work management** | Tasks with dependency graph, goal milestones, project rollups, weekly review. |
| **First-run onboarding** | Three-step wizard: connect a source → declare values → seed a goal. |
| **Ops safety** | Migrations auto-run on boot. Daily retention prune. System Health dashboard. CI gates every merge. |

---

## Live deployment

| Service | URL |
|---|---|
| Frontend | your Vercel deployment URL |
| Backend API | your Railway service URL |
| API docs | `<railway-url>/docs` |

---

## Quick start (local dev)

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for Postgres + Weaviate)
- A [Supabase](https://supabase.com) project (free tier is fine)
- A [Composio](https://composio.dev) API key (free) for integrations
- A [Groq](https://console.groq.com) API key for the LLM

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in the values below
docker compose up -d          # starts Postgres + Weaviate
python main.py                # → http://localhost:8000/docs
```

**Required `.env` values:**

```env
# LLM
GROQ_API_KEY=...
GEMINI_API_KEY=...            # for embeddings

# Database (local Docker)
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ethic_companion
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Auth
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_AUDIENCE=authenticated
ENVIRONMENT=development
AUTH_ENFORCEMENT_ENABLED=false   # skip JWT in local dev

# Integrations
COMPOSIO_API_KEY=...             # get at composio.dev
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
```

**Optional:**
```env
JINA_API_KEY=...     # cross-encoder rerank (100 RPM free)
TAVILY_API_KEY=...   # web search tool
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                   # → http://localhost:3000
```

**`.env.local` values:**

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

### Apply migrations

```bash
cd backend
python -m scripts.run_migrations
```

Or paste each file from `backend/migrations/` into the Supabase SQL Editor.

---

## Deploying your own instance

### Backend → Railway

1. Create a new Railway project, add a service from this GitHub repo
2. Set root directory to `backend/`
3. Add all env vars from the table below
4. Railway auto-deploys on push to `main`

**Railway env vars:**

| Variable | Where to get it |
|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) |
| `POSTGRES_SERVER` | Supabase → Settings → Database → Host (use pooler: `aws-0-eu-west-1.pooler.supabase.com`) |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_DB` | `postgres` |
| `POSTGRES_USER` | `postgres.your-project-ref` |
| `POSTGRES_PASSWORD` | Supabase → Settings → Database → Password |
| `SUPABASE_URL` | Supabase → Settings → API |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` |
| `SECRET_KEY` | any 32+ char random string |
| `COMPOSIO_API_KEY` | [composio.dev](https://composio.dev) → Dashboard → API Keys |
| `BACKEND_URL` | your Railway service URL |
| `FRONTEND_URL` | your Vercel deployment URL |
| `ENVIRONMENT` | `production` |
| `AUTH_ENFORCEMENT_ENABLED` | `true` |

### Frontend → Vercel

```bash
cd frontend
vercel --prod
```

Or connect the GitHub repo in the Vercel dashboard — set **Root Directory** to `frontend/`.

**Vercel env vars:**

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | your Railway backend URL |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Settings → API |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Settings → API |

### Auth — Supabase

1. Enable **Email (magic link)** in Supabase → Authentication → Providers
2. Enable **Google** OAuth: set Client ID + Secret from Google Cloud Console
3. Add your Vercel URL to Supabase → Authentication → URL Configuration → Redirect URLs:
   `https://your-app.vercel.app/auth/callback`
4. Set Site URL to `https://your-app.vercel.app`

### Integrations — Composio

1. Sign up at [composio.dev](https://composio.dev) (free)
2. Copy your API key → set as `COMPOSIO_API_KEY` in Railway
3. Users connect their apps (Gmail, Calendar, Slack, GitHub, Notion) via the in-app Integrations page — no extra setup needed per app

### CI/CD — GitHub Actions

Add these secrets in GitHub → Settings → Secrets → Actions:

| Secret | Value |
|---|---|
| `VERCEL_TOKEN` | Vercel → Settings → Tokens |
| `VERCEL_ORG_ID` | Run `cat frontend/.vercel/project.json` after first `vercel` deploy |
| `VERCEL_PROJECT_ID` | Run `cat frontend/.vercel/project.json` after first `vercel` deploy |
| `RAILWAY_TOKEN` | Railway → Account Settings → Tokens |

On every push to `main`: tests run → ESL coverage enforced (≥75%) → both services deploy automatically.

---

## Architecture

```
Browser (Next.js 16, App Router)
        │  HTTPS + Supabase session cookie
        ▼
Backend (FastAPI on Railway)
        │
        ├── Ethical Safeguard Layer  ◀── mandatory gateway for every user-facing action
        │       ├── TimeBasedRules       (quiet hours, do-not-disturb)
        │       ├── ManipulationDetector (blocks dark patterns)
        │       └── EngagementDetector   (blocks addictive loops)
        │
        ├── LangGraph orchestrator   ◀── multi-step planner, tool use, RAG
        │       └── Composio tools       (Gmail, Calendar, Slack, GitHub, Notion)
        │
        ├── Supabase (Postgres)      ◀── users, values, goals, tasks, source_items, ESL audit log
        └── Weaviate                 ◀── hybrid dense+BM25 search (alpha=0.7)

Auth: Supabase Auth (magic link + Google OAuth, PKCE via @supabase/ssr)
Integrations: Composio (OAuth management, token refresh, 250+ APIs)
```

**The ESL is not optional.** It is the gateway every action must pass through.
See [`CLAUDE.md`](CLAUDE.md) for the full operating contract.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, LangGraph, psycopg, APScheduler |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind, Radix UI |
| Database | Postgres + pgvector on Supabase |
| Vector search | Weaviate (hybrid BM25 + dense, optional Jina rerank) |
| LLMs | Groq (Llama 3.3 70B), Gemini (embeddings) |
| Auth | Supabase Auth — magic link + Google OAuth, PKCE |
| Integrations | Composio — Gmail, Google Calendar, Slack, GitHub, Notion |
| Backend deploy | Railway |
| Frontend deploy | Vercel |
| CI/CD | GitHub Actions (pytest + ESL coverage gate + auto-deploy) |

---

## Core principles

1. **User well-being is the primary metric.** Not DAU, not time-in-app, not message count.
2. **User control is non-negotiable.** Boundaries declared in `user_values` are enforced. Always.
3. **Non-manipulation by design.** No FOMO, no urgency, no dark patterns. The `ManipulationDetector` and `EngagementDetector` say no.
4. **Transparency by default.** Every ESL decision is logged. Every tool call is visible in the Transparency tab.

---

## Development

```bash
# Backend tests
cd backend
pytest --tb=short -q
pytest tests/test_esl.py -v    # ESL changes? always run this first
black . && flake8 .

# Frontend
cd frontend
npx tsc --noEmit
npm run build
```

**Critical rule:** changes touching `esl/` or `services/orchestrator/` must include a passing `tests/test_esl.py` run before commit. The ESL is the single architectural invariant of this project.

---

## Project structure

```
backend/
  esl/                  ESL engine, models, rules, audit
  services/             Composio sync, RAG, rerank, document processing
  orchestrator/         LangGraph nodes and graph
  routes/               FastAPI HTTP routes
  migrations/           Numbered SQL migrations (auto-run on boot)
  tests/                pytest suite
frontend/
  app/dashboard/        Authenticated dashboard pages
  app/auth/callback/    Supabase PKCE OAuth callback
  components/           UI components (chat, transparency, integrations…)
  lib/api.ts            Typed API client
vercel.json             Tells Vercel to build from frontend/ subdirectory
.github/workflows/
  ci.yml                Tests + auto-deploy on merge to main
  deploy-backend.yml    Backend-only Railway deploy gate
```

---

## License

[Apache 2.0](LICENSE)

---

## Author

**Cátia Machado** — *Trust over Engagement. Always.*
