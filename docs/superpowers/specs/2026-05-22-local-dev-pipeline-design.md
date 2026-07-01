# Local Dev Pipeline Design

**Date:** 2026-05-22  
**Status:** Approved  
**Scope:** Makefile + migration safety + Docker Compose dev overlay + seed data

## Problem

- No safe way to preview migrations before running them against production
- Fresh clone requires many manual steps (copy envs, create venv, npm install, docker up)
- Local dev has no realistic test data — the dashboard and ESL views are empty
- Accidental production breakage from pushing untested migrations

## Out of Scope

- Cloud staging environment (not needed for solo developer)
- Pre-commit hooks / migration lock (Option C, deferred)
- CI/CD changes (existing `ci.yml` and `deploy-backend.yml` are sufficient)

---

## Component 1: Makefile

**Location:** `Makefile` (repo root)

Single entry point for all common dev tasks. No new tooling dependencies — pure `make`.

### Commands

| Command | What it does |
|---|---|
| `make setup` | First-time setup: copy `.env.example` → `.env` and `.env.local.example` → `.env.local` if missing, create backend venv, `pip install -r requirements.txt`, `npm install` in frontend |
| `make dev-up` | `docker compose up -d` — starts Postgres + Weaviate |
| `make dev-down` | `docker compose down` |
| `make dev-reset` | `dev-down` → wipe Docker volumes → `dev-up` → run seed script |
| `make migrate-dry` | Print pending migrations and their SQL without applying anything |
| `make migrate` | Run `migrate-dry`, print output, prompt "Apply? [y/N]", apply only on explicit `y` |
| `make migrate-prod` | Same as `make migrate` but uses `PROD_DATABASE_URL`; prints a loud `⚠ PRODUCTION DATABASE` warning and requires typing `yes-i-am-sure` before proceeding |
| `make test` | `pytest tests/ -v` + `npm run test --passWithNoTests` |
| `make lint` | `black --check .` + `flake8 .` + `mypy .` + `npm run lint` |

### Error handling

- `make setup` is idempotent: skips file copies if destinations already exist, skips installs if already done
- `make migrate` and `make migrate-prod` exit non-zero if the user answers anything other than `y` / `yes-i-am-sure` respectively — safe to call from scripts

---

## Component 2: Migration Script Enhancement

**Location:** `backend/scripts/run_migrations.py` (existing file, enhanced)

Add a `--dry-run` CLI flag. When set:
1. Connect to the database (read-only intent — no writes)
2. Determine which migration files are pending (not yet in `schema_migrations` table)
3. Print each pending filename and its full SQL content
4. Exit 0 without applying anything

`make migrate` calls `run_migrations.py --dry-run` first, captures the output, prints it, then prompts before calling `run_migrations.py` (no flag) to apply.

`make migrate-prod` follows the same flow but sets `DATABASE_URL=$PROD_DATABASE_URL`. `PROD_DATABASE_URL` must be set manually in the user's local `.env` — it is never committed to the repo and is not copied by `make setup`.

---

## Component 3: Docker Compose Dev Overlay

**Location:** `backend/docker-compose.dev.yml`

Extends `docker-compose.yml`. Adds a `seed` service that runs once and exits.

```yaml
# Usage: docker compose -f docker-compose.yml -f docker-compose.dev.yml up seed
services:
  seed:
    build: .
    command: python -m scripts.seed_dev
    depends_on:
      - db
    env_file: .env
    restart: "no"
```

`make dev-up` uses only `docker-compose.yml` (infrastructure only — fast). `make dev-reset` uses the overlay to run the seed service after volumes are fresh.

The backend and frontend are **not** added to Docker Compose — they are run directly in the terminal (`uvicorn` / `npm run dev`) for better log visibility and hot-reload control.

---

## Component 4: Seed Script

**Location:** `backend/scripts/seed_dev.py`

Creates a deterministic, realistic local dataset. Idempotent: checks for existence before inserting (upsert on email/name).

### Seed data

**User**
- Email: `dev@ethic-companion.local`
- Password hash: bcrypt of `dev123`
- Display name: `Dev User`

**User values** (3 entries in `user_values` table)
- `"no notifications after 9pm"` — boundary, high importance
- `"prefer async communication"` — preference, medium importance
- `"limit social media suggestions"` — boundary, high importance

**Goals** (2 entries)
- `"Read 2 books this month"` — active
- `"Exercise 3x per week"` — active

**Conversation history** (5 entries in M2/pgvector)
- A short realistic back-and-forth between user and assistant covering one of the goals

**ESL audit log** (3 entries)
- 1 APPROVED action, 1 MODIFIED action, 1 VETOED action — so the ESL dashboard has visible data

### Dependencies

Uses the existing `context_manager` and `database` modules — no new DB access patterns introduced.

---

## File Changes Summary

| File | Change |
|---|---|
| `Makefile` | New file at repo root |
| `backend/scripts/run_migrations.py` | Add `--dry-run` flag |
| `backend/docker-compose.dev.yml` | New file |
| `backend/scripts/seed_dev.py` | New file |

No changes to CI workflows, existing Docker Compose, or any application code.

---

## Success Criteria

- `make setup && make dev-up` gets a fresh clone to running infrastructure in one session, with no manual steps beyond filling in real API keys in `.env`
- `make migrate-dry` shows exactly what SQL will run before any migration touches the DB
- `make migrate` requires explicit confirmation before applying
- `make dev-reset` leaves the local DB in a known state with visible seed data
- `make migrate-prod` is visually distinct and requires deliberate confirmation
