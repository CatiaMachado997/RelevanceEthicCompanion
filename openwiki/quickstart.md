# Ethic Companion — engineering quickstart

Ethic Companion is a personal AI companion designed around **trust over engagement**. It combines a Next.js dashboard with a FastAPI API, a LangGraph agent, user-declared ethical boundaries, personal work-management data, and grounded context from uploaded documents and connected services.

This wiki is a maintained navigation layer over the codebase—not a replacement for the root [README](../README.md), which contains the fuller local setup and deployment checklist.

## Start here

1. **Prepare local services:** Python 3.11+, Node 20+, Docker, Supabase, and provider credentials are expected. From the repository root, `make setup` creates local config files and installs dependencies; `make dev-up` starts Postgres and Weaviate. See [operations](operations.md).
2. **Run the API:** activate `backend/venv`, then run `python main.py` from `backend/`. FastAPI docs are at `http://localhost:8000/docs`.
3. **Run the UI:** run `npm run dev` from `frontend/`; it serves on `http://localhost:3000`.
4. **Use the real test gates:** `make test` runs backend pytest and frontend Jest. CI additionally runs Black, Flake8, TypeScript, frontend build, and an ESL coverage gate. See [testing](testing.md).

Never commit real values from `backend/.env` or `frontend/.env.local`. Use the checked-in examples as the non-sensitive configuration reference.

## What is where

| Area | What it owns | Read next |
|---|---|---|
| Runtime architecture | FastAPI startup, dashboard auth boundary, LangGraph modes, ESL gate | [Architecture](architecture.md) |
| End-to-end behavior | chat/SSE, planner loop, retrieval, sync, work management, AutoLab | [Key workflows](workflows.md) |
| External and auth boundaries | Supabase auth, source sync, marketplace tools, providers, MCP | [Integrations](integrations.md) |
| Product and storage model | values, safety, goals/projects/tasks, conversations, memory, audit trail | [Domain concepts](domains.md) |
| Engineer navigation | entrypoints and high-signal folders | [Source map](source-map.md) |
| Running and changing safely | Docker, migrations, feature flags, CI/deploy, operational cautions | [Operations](operations.md) |
| Verification strategy | test commands, integration services, regression anchors | [Testing](testing.md) |

## System in one view

```text
Next.js 16 dashboard ──Bearer token/SSE──> FastAPI
                                             │
                              LangGraph context → intent → plan/tools ↔ plan
                                             │                 │
                                      Ethical Safeguard Layer  │
                                             │                 │
                 Supabase/Postgres <── audit, work, chat, source metadata
                         │                   Weaviate <── indexed document/source chunks
                         └── Supabase Auth; connectors/Composio; Groq/Gemini/Jina optional
```

The normal agent graph forces every response through the Ethical Safeguard Layer (ESL); a veto produces an explanatory response instead of the proposed output. The current planner has a hard default cap of three planning passes. These are behaviorally important safeguards, not UI conventions. See [architecture](architecture.md) and [workflows](workflows.md).

## Recent direction

Recent history emphasizes agent execution safety and observability: explicit ReAct planning and parallel-action work (Sprint I), streaming reasoning and layered confirmation interrupts (Sprint J), episodic tool memory (Sprint K), then live-validation fixes for planner termination, memory activation, and feature-flag/UI behavior. The current Git working tree also contains uncommitted authentication/proxy edits and newly added OpenWiki automation; this initial wiki describes committed source behavior plus clearly marked operational caveats, not an assumption that those local edits are complete.

## Backlog

- **Integration lifecycle unification** — `backend/routes/connectors.py` and `frontend/app/dashboard/integrations/page.tsx`: GitHub/Notion appear in UI/Composio paths while the connector operator API supports only Gmail, Slack, and Google Calendar. The canonical OAuth/status/backfill lifecycle needs a product/engineering decision.
- **Schema authority** — `backend/database/schema.sql`, `backend/migrations/`, and startup DDL in `backend/main.py`: these coexist and need an explicit provisioning/deprecation policy before a deeper schema reference can safely call one authoritative.
- **AutoLab production posture** — `backend/autolab/runner.py` and `backend/routes/autolab.py`: the feature can apply LLM-generated patches to experiment surfaces; confirm access control, deployment isolation, serialization, and budget enforcement before treating it as production-safe.
