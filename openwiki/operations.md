# Operations and runbook

## Local development

From repository root:

```bash
make setup       # creates local env files if absent; creates venv; installs Python/npm deps
make dev-up      # backend Docker Compose: Postgres + Weaviate
# terminal 1
cd backend && source venv/bin/activate && python main.py
# terminal 2
cd frontend && npm run dev
```

`backend/docker-compose.yml` exposes Postgres on 5432 and Weaviate HTTP/gRPC on 8080/50051 with persistent local volumes. The root README lists the required external service configuration; use `backend/.env.example` and `frontend/.env.local.example`, never live env files, as the setup reference.

## Database migration procedure

The versioned runner (`backend/scripts/run_migrations.py`) alphabetically reads `backend/migrations/*.sql`, records filenames in `schema_migrations`, and executes each migration atomically in its own connection. Application startup runs it and refuses traffic on failure.

```bash
make migrate-dry  # inspect pending migrations
make migrate      # dry-run then interactive local apply
# production only, explicit environment variable + exact confirmation:
make migrate-prod
```

Before adding a migration, account for prior schema artifacts and the inline compatibility DDL in `backend/main.py`; see [domains](domains.md). Test both a fresh bootstrap and upgrade from existing state where the changed tables are historical.

## Feature-flag rollout

`backend/config.py` defaults parallel planning, streaming reasoning, and episodic planner memory **off**. Roll out one at a time:

1. Enable in a disposable/staging environment with database and Weaviate available.
2. For streaming reasoning, verify durable checkpointer behavior and explicit `/api/chat/resume` approval/skip/cancel behavior. Development/test uses in-memory checkpoints; production tries Postgres then falls back to memory.
3. For parallel planning, exercise serial and parallel execution plus retry semantics.
4. For episodic memory, verify run persistence, recall quality, and no recall when disabled.
5. Inspect streaming events, planner traces, tool telemetry, and ESL outcomes in Transparency before broad enablement.

`MULTI_AGENT=true` selects the supervisor graph, but streaming reasoning wins if both are enabled. Treat that interaction as a deployment constraint.

## Service health and scheduler

At startup the API opens the connection pool, runs migration/compatibility checks, and attempts to initialize scheduled ingestion. Scheduler failure is non-fatal: manual connector backfill remains available. The documented startup schedule includes calendar sync every 15 minutes (`backend/main.py`). Weaviate/embedding failures degrade retrieval to an empty context rather than failing chat; monitor health/error fields so this does not become a silent quality regression.

## CI and deployment

`.github/workflows/ci.yml` runs on main pushes and PRs:

- backend tests with Postgres and Weaviate service containers, Black and Flake8, coverage reporting;
- a dedicated ESL test job with 75% `esl` coverage threshold;
- frontend npm CI, lint, TypeScript check, and production build;
- after those gates on a main push, Vercel frontend and Railway backend deployment.

`deploy-backend.yml` is a backend-only deploy gate. The newly present `openwiki-update.yml` schedules/dispatches OpenWiki updates and opens a PR limited to documentation/agent workflow files. Review its permissions and generated changes like any automation PR.

## High-risk areas

- **AutoLab:** can mutate experiment `surface.py` files using an LLM-proposed patch. Ensure access control, isolated checkout/deployment, serialized runs, reviewable results, and external evaluator timeouts; runner-level `budget_secs` is not enforced.
- **Integration divergence:** do not promise uniform status/backfill behavior for GitHub/Notion until native and Composio lifecycle expectations are reconciled.
- **Auth:** production must keep auth enforcement enabled. Startup warns when read-route enforcement is disabled outside development.
- **Secrets:** production can load named values from GCP Secret Manager. Documentation and logs must name environment variables/services only, never reveal values.
