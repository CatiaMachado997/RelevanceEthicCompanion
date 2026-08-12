# Source map

## Entrypoints and contracts

| Location | Why it matters |
|---|---|
| `README.md` | Product overview, prerequisites, local/deployment setup. |
| `Makefile` | Canonical developer commands for setup, Docker, migrations, test, lint. |
| `backend/main.py` | FastAPI lifespan, migration/startup policy, router composition, scheduler. |
| `backend/config.py` | Environment-derived settings, secret-manager mapping, auth controls, agent flags, retention. |
| `frontend/app/dashboard/layout.tsx` | Auth/API setup, onboarding guard, global dashboard shell. |
| `frontend/lib/api.ts` | Typed frontend API façade, bearer token/timeout/error behavior, SSE-facing types. |

## Backend areas

| Directory/file | Responsibilities |
|---|---|
| `backend/orchestrator/graph.py` | Normal, async/streaming, and multi-agent LangGraph assembly; planner kill-switch and checkpoint selection. |
| `backend/orchestrator/nodes/` | Context, intent, tool planning/execution, ESL gateway, response formatting. |
| `backend/orchestrator/agents/` | Supervisor and specialized research/calendar/goals/document/connectors workers. |
| `backend/esl/` | Models, rules, engine, audit persistence, marketplace tool gate. |
| `backend/routes/` | FastAPI surface grouped by chat, organization, documents/search, settings/onboarding, integrations/tools, transparency, AutoLab. |
| `backend/services/` | Business/integration workflows: retrieval, indexing, embedding, sync, planner memory/runs, safety preferences, telemetry, work rollups, scheduling. |
| `backend/database/schema.sql` | Baseline Supabase/Postgres model and RLS examples; not the only provisioning artifact. |
| `backend/migrations/` | Versioned upgrade migrations used by the runner. |
| `backend/scripts/run_migrations.py` | Migration sequencing and tracking. |
| `backend/autolab/` | Track configuration, evaluators, patching runner, Obsidian/local result persistence. |
| `backend/tests/` | Unit/integration/regression coverage—start with the closest behavior test. |

## Frontend areas

| Directory/file | Responsibilities |
|---|---|
| `frontend/app/` | Next App Router pages: login/auth callback, onboarding, dashboard routes. |
| `frontend/app/dashboard/chat/` | Chat interaction, stream rendering, source selection, tool confirmations. |
| `frontend/app/dashboard/{values,goals,projects,tasks,today,weekly-review}/` | Personal organization workflows. |
| `frontend/app/dashboard/{documents,search,integrations,transparency,settings,insights}/` | Context ingestion/retrieval, provider settings, audit UX, safety controls, AutoLab insights. |
| `frontend/components/` | Shared dashboard/navigation and domain-specific UI (chat, goals, tasks, projects, transparency, settings). |
| `frontend/hooks/` | Authentication and onboarding state coordination. |
| `frontend/__tests__/` | Jest tests for frontend units/pages. |

## Infrastructure and design references

| Location | Use |
|---|---|
| `.github/workflows/ci.yml` | Actual full-stack quality/deploy gate. |
| `.github/workflows/deploy-backend.yml` | Backend-only deploy gate. |
| `.github/workflows/openwiki-update.yml` | Scheduled/manual documentation PR automation (currently uncommitted). |
| `backend/docker-compose.yml` | Local Postgres and Weaviate topology. |
| `docs/ARCHITECTURE.md`, `DESIGN_SYSTEM.md`, `docs/design/` | Existing product/design references; verify against current code before copying implementation details. |
| `docs/superpowers/{plans,specs}/` | Sprint-level design intent for recent agent and AutoLab work. |

## Search strategy for future agents

Start from the route or page the user experiences, then follow into its service and persistence layer. For chat/tool changes, begin at `routes/chat.py` → `orchestrator/graph.py` → relevant node/service → matching `backend/tests/test_*`. For dashboard changes, begin at page/component → `frontend/lib/api.ts` → FastAPI route → service. Avoid broad file inventories; this codebase has retained historical schema and documentation artifacts that can look current but are not necessarily runtime authority.
