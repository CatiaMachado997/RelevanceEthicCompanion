# Local Dev Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Makefile + migration dry-run + Docker Compose dev overlay + seed script so local dev starts in one command and migrations are safe to run.

**Architecture:** Four independent additions — a root Makefile as the developer's single entry point, a `--dry-run` flag on the existing migration runner, a `docker-compose.dev.yml` overlay that adds a seed service, and a `seed_dev.py` script that populates a known local dataset. No app code is changed.

**Tech Stack:** GNU Make, Python 3.11 (psycopg3), Docker Compose v2, pytest

---

## File Map

| File | Change |
|---|---|
| `Makefile` | Create — all dev commands |
| `backend/scripts/run_migrations.py` | Modify — add `--dry-run` flag and `dry_run_migrations()` helper |
| `backend/tests/test_run_migrations.py` | Create — dry-run unit tests |
| `backend/docker-compose.dev.yml` | Create — seed service overlay |
| `backend/scripts/seed_dev.py` | Create — idempotent seed script |
| `backend/tests/test_seed_dev.py` | Create — seed idempotency tests |

---

### Task 1: Migration dry-run

**Files:**
- Modify: `backend/scripts/run_migrations.py`
- Create: `backend/tests/test_run_migrations.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_run_migrations.py`:

```python
"""Tests for run_migrations dry-run flag."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


def _make_migration_files(tmp_path: Path, filenames: list[str]) -> str:
    for name in filenames:
        (tmp_path / name).write_text(f"-- {name}\nSELECT 1;")
    return str(tmp_path)


def _make_mock_conn(applied: set[str]):
    """Return a mock psycopg connection whose cursor reports `applied` as done."""
    mock_rows = [{"filename": f} for f in applied]
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchall.return_value = mock_rows
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    return mock_conn, mock_cur


class TestDryRunMigrations:
    def test_dry_run_returns_pending_filenames(self, tmp_path):
        migrations_dir = _make_migration_files(
            tmp_path, ["001_init.sql", "002_users.sql"]
        )
        mock_conn, mock_cur = _make_mock_conn({"001_init.sql"})

        with patch(
            "scripts.run_migrations.get_db_connection", return_value=mock_conn
        ):
            from scripts.run_migrations import dry_run_migrations

            pending = dry_run_migrations(migrations_dir=migrations_dir)

        assert pending == [("002_users.sql", "-- 002_users.sql\nSELECT 1;")]

    def test_dry_run_does_not_apply_migrations(self, tmp_path):
        migrations_dir = _make_migration_files(tmp_path, ["001_init.sql"])
        mock_conn, mock_cur = _make_mock_conn(set())

        with patch(
            "scripts.run_migrations.get_db_connection", return_value=mock_conn
        ):
            from scripts.run_migrations import dry_run_migrations

            dry_run_migrations(migrations_dir=migrations_dir)

        # cursor.execute should only have been called for the tracking-table
        # setup and SELECT — never for the migration SQL itself
        execute_calls = mock_cur.execute.call_args_list
        called_sqls = [str(c) for c in execute_calls]
        assert not any("SELECT 1" in s for s in called_sqls)

    def test_dry_run_all_applied_returns_empty(self, tmp_path):
        migrations_dir = _make_migration_files(tmp_path, ["001_init.sql"])
        mock_conn, _ = _make_mock_conn({"001_init.sql"})

        with patch(
            "scripts.run_migrations.get_db_connection", return_value=mock_conn
        ):
            from scripts.run_migrations import dry_run_migrations

            pending = dry_run_migrations(migrations_dir=migrations_dir)

        assert pending == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend
pytest tests/test_run_migrations.py -v
```

Expected: `ImportError` or `AttributeError: module 'scripts.run_migrations' has no attribute 'dry_run_migrations'`

- [ ] **Step 3: Add `dry_run_migrations()` and `--dry-run` CLI flag**

In `backend/scripts/run_migrations.py`, add after the `run_migrations` function and update `__main__` block:

```python
def dry_run_migrations(migrations_dir: str | None = None) -> list[tuple[str, str]]:
    """Return list of (filename, sql) for pending migrations without applying them."""
    if migrations_dir is None:
        migrations_dir = str(Path(__file__).parent.parent / "migrations")

    sql_files = sorted(f for f in os.listdir(migrations_dir) if f.endswith(".sql"))

    if not sql_files:
        return []

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename   TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {row["filename"] for row in cur.fetchall()}

    pending = []
    for filename in sql_files:
        if filename in applied:
            continue
        filepath = os.path.join(migrations_dir, filename)
        sql = Path(filepath).read_text(encoding="utf-8")
        pending.append((filename, sql))

    return pending
```

Replace the `__main__` block at the bottom of the file:

```python
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Run pending SQL migrations")
    parser.add_argument("--migrations-dir", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print pending migrations without applying them",
    )
    args = parser.parse_args()
    try:
        if args.dry_run:
            pending = dry_run_migrations(migrations_dir=args.migrations_dir)
            if not pending:
                print("No pending migrations.")
            else:
                for filename, sql in pending:
                    print(f"\n{'='*60}")
                    print(f"  PENDING: {filename}")
                    print(f"{'='*60}")
                    print(sql)
        else:
            run_migrations(migrations_dir=args.migrations_dir)
    except Exception:
        sys.exit(1)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend
pytest tests/test_run_migrations.py -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/run_migrations.py backend/tests/test_run_migrations.py
git commit -m "feat(migrations): add --dry-run flag to run_migrations"
```

---

### Task 2: Makefile

**Files:**
- Create: `Makefile` (repo root)

- [ ] **Step 1: Create the Makefile**

Create `Makefile` at the repo root (alongside `backend/` and `frontend/`):

```makefile
.DEFAULT_GOAL := help
SHELL         := /bin/bash
BACKEND_DIR   := backend
FRONTEND_DIR  := frontend

.PHONY: help setup dev-up dev-down dev-reset migrate-dry migrate migrate-prod test lint

help:
	@echo ""
	@echo "  make setup          First-time setup (copy envs, venv, npm install)"
	@echo "  make dev-up         Start Postgres + Weaviate"
	@echo "  make dev-down       Stop and remove containers"
	@echo "  make dev-reset      Wipe volumes, restart, seed DB"
	@echo "  make migrate-dry    Preview pending migrations (no changes)"
	@echo "  make migrate        Apply pending migrations (local DB)"
	@echo "  make migrate-prod   Apply migrations to PROD (requires confirmation)"
	@echo "  make test           Run all backend + frontend tests"
	@echo "  make lint           Run black, flake8, mypy, eslint"
	@echo ""

setup:
	@echo "==> Setting up local environment..."
	@[ -f $(BACKEND_DIR)/.env ] || cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env && echo "  copied backend/.env"
	@[ -f $(FRONTEND_DIR)/.env.local ] || cp $(FRONTEND_DIR)/.env.local.example $(FRONTEND_DIR)/.env.local && echo "  copied frontend/.env.local"
	@[ -d $(BACKEND_DIR)/venv ] || (cd $(BACKEND_DIR) && python3 -m venv venv && echo "  created venv")
	@cd $(BACKEND_DIR) && source venv/bin/activate && pip install -q -r requirements.txt && echo "  pip install done"
	@cd $(FRONTEND_DIR) && npm install --silent && echo "  npm install done"
	@echo "==> Setup complete. Fill in real API keys in backend/.env"

dev-up:
	@cd $(BACKEND_DIR) && docker compose up -d
	@echo "==> Postgres + Weaviate running"

dev-down:
	@cd $(BACKEND_DIR) && docker compose down
	@echo "==> Containers stopped"

dev-reset:
	@cd $(BACKEND_DIR) && docker compose down -v
	@cd $(BACKEND_DIR) && docker compose up -d
	@echo "==> Waiting for Postgres to be ready..."
	@sleep 3
	@cd $(BACKEND_DIR) && source venv/bin/activate && python -m scripts.run_migrations
	@cd $(BACKEND_DIR) && source venv/bin/activate && python -m scripts.seed_dev
	@echo "==> Dev DB reset and seeded"

migrate-dry:
	@cd $(BACKEND_DIR) && source venv/bin/activate && python -m scripts.run_migrations --dry-run

migrate:
	@$(MAKE) migrate-dry
	@echo ""
	@read -p "Apply these migrations? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		cd $(BACKEND_DIR) && source venv/bin/activate && python -m scripts.run_migrations; \
	else \
		echo "Aborted."; exit 1; \
	fi

migrate-prod:
	@echo ""
	@echo "  ╔══════════════════════════════════════════╗"
	@echo "  ║  ⚠  WARNING: PRODUCTION DATABASE  ⚠     ║"
	@echo "  ╚══════════════════════════════════════════╝"
	@echo ""
	@$(MAKE) migrate-dry
	@echo ""
	@read -p "Type 'yes-i-am-sure' to apply to PRODUCTION: " confirm; \
	if [ "$$confirm" = "yes-i-am-sure" ]; then \
		cd $(BACKEND_DIR) && source venv/bin/activate && \
		DATABASE_URL="$$PROD_DATABASE_URL" python -m scripts.run_migrations; \
	else \
		echo "Aborted."; exit 1; \
	fi

test:
	@cd $(BACKEND_DIR) && source venv/bin/activate && pytest tests/ -v
	@cd $(FRONTEND_DIR) && npm run test -- --passWithNoTests

lint:
	@cd $(BACKEND_DIR) && source venv/bin/activate && black --check . && flake8 . --max-line-length=120 --exclude=venv,__pycache__,.git && mypy . --ignore-missing-imports --exclude venv
	@cd $(FRONTEND_DIR) && npm run lint
```

- [ ] **Step 2: Verify `make help` works**

```bash
make help
```

Expected: prints the command list with no errors.

- [ ] **Step 3: Verify `make setup` works on a clean check**

```bash
make setup
```

Expected: prints "Setup complete." — may skip steps already done, that's correct.

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "feat: add Makefile with dev, migrate, test, and lint commands"
```

---

### Task 3: Docker Compose dev overlay

**Files:**
- Create: `backend/docker-compose.dev.yml`

- [ ] **Step 1: Create the overlay file**

Create `backend/docker-compose.dev.yml`:

```yaml
# Dev overlay — adds a one-shot seed service to docker-compose.yml
# Usage: docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm seed
services:
  seed:
    build:
      context: .
      dockerfile: Dockerfile
    command: python -m scripts.seed_dev
    depends_on:
      - db
    env_file: .env
    restart: "no"
```

- [ ] **Step 2: Verify compose config is valid**

```bash
cd backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml config --quiet
```

Expected: exits 0 with no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/docker-compose.dev.yml
git commit -m "feat: add docker-compose.dev.yml overlay with seed service"
```

---

### Task 4: Seed script

**Files:**
- Create: `backend/scripts/seed_dev.py`
- Create: `backend/tests/test_seed_dev.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_seed_dev.py`:

```python
"""Tests for seed_dev idempotency."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import pytest


def _make_mock_conn(existing_email: str | None = None):
    """Return a mock connection that reports whether the dev user exists."""
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)

    # fetchone returns a row if user exists, else None
    mock_cur.fetchone.return_value = (
        {"id": "test-uuid-1234", "email": existing_email} if existing_email else None
    )

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    return mock_conn, mock_cur


class TestSeedDev:
    def test_seed_creates_user_when_not_exists(self):
        mock_conn, mock_cur = _make_mock_conn(existing_email=None)
        # Second fetchone (after insert) returns the new user
        mock_cur.fetchone.side_effect = [None, {"id": "new-uuid", "email": "dev@ethic-companion.local"}]

        with patch("scripts.seed_dev.get_db_connection", return_value=mock_conn):
            from scripts.seed_dev import seed

            seed()

        # Verify an INSERT for users was called
        execute_calls = " ".join(str(c) for c in mock_cur.execute.call_args_list)
        assert "INSERT" in execute_calls

    def test_seed_skips_user_insert_when_exists(self):
        mock_conn, mock_cur = _make_mock_conn(
            existing_email="dev@ethic-companion.local"
        )

        with patch("scripts.seed_dev.get_db_connection", return_value=mock_conn):
            from scripts.seed_dev import seed

            seed()

        # Verify no INSERT INTO users was called
        execute_calls = " ".join(str(c) for c in mock_cur.execute.call_args_list)
        assert "INSERT INTO public.users" not in execute_calls

    def test_seed_is_idempotent(self):
        """Running seed twice should not raise."""
        mock_conn, mock_cur = _make_mock_conn(
            existing_email="dev@ethic-companion.local"
        )

        with patch("scripts.seed_dev.get_db_connection", return_value=mock_conn):
            from scripts.seed_dev import seed

            seed()
            seed()  # second call must not raise
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend
pytest tests/test_seed_dev.py -v
```

Expected: `ImportError` — `scripts.seed_dev` does not exist yet.

- [ ] **Step 3: Create the seed script**

Create `backend/scripts/seed_dev.py`:

```python
"""
Seed the local dev database with a known dataset.

Idempotent: safe to run multiple times. Uses upsert / existence checks
so re-running does not duplicate data.

Usage:
    python -m scripts.seed_dev
"""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

DEV_EMAIL = "dev@ethic-companion.local"
DEV_NAME = "Dev User"


def get_db_connection():
    from utils.db import get_db_connection as _get
    return _get()


def seed() -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # ── User ──────────────────────────────────────────────────
            cur.execute(
                "SELECT id, email FROM public.users WHERE email = %s",
                (DEV_EMAIL,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    """
                    INSERT INTO public.users (email, full_name)
                    VALUES (%s, %s)
                    RETURNING id, email
                    """,
                    (DEV_EMAIL, DEV_NAME),
                )
                row = cur.fetchone()
                logger.info("  created user: %s", DEV_EMAIL)
            else:
                logger.info("  user exists, skipping: %s", DEV_EMAIL)

            user_id = row["id"]

            # ── User values ───────────────────────────────────────────
            values = [
                ("boundary", "no notifications after 9pm", 9),
                ("preference", "prefer async communication", 5),
                ("boundary", "limit social media suggestions", 8),
            ]
            for vtype, vtext, priority in values:
                cur.execute(
                    """
                    INSERT INTO public.user_values (user_id, type, value, priority)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (user_id, vtype, vtext, priority),
                )
            logger.info("  upserted %d user values", len(values))

            # ── Goals ─────────────────────────────────────────────────
            goals = [
                ("Read 2 books this month", "Track reading progress", 7),
                ("Exercise 3x per week", "Maintain weekly exercise habit", 8),
            ]
            for title, description, priority in goals:
                cur.execute(
                    """
                    INSERT INTO public.goals (user_id, title, description, priority)
                    SELECT %s, %s, %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM public.goals
                        WHERE user_id = %s AND title = %s
                    )
                    """,
                    (user_id, title, description, priority, user_id, title),
                )
            logger.info("  upserted %d goals", len(goals))

            # ── ESL audit log ─────────────────────────────────────────
            import json

            esl_entries = [
                (
                    user_id,
                    json.dumps({"action_type": "push_notification", "content": "Daily summary ready"}),
                    "APPROVED",
                    "Action aligns with user preferences",
                    [],
                    ["time_window_check"],
                    0.95,
                ),
                (
                    user_id,
                    json.dumps({"action_type": "push_notification", "content": "Check your social feed"}),
                    "VETOED",
                    "Violates boundary: limit social media suggestions",
                    ["limit social media suggestions"],
                    ["value_boundary_check"],
                    0.98,
                ),
                (
                    user_id,
                    json.dumps({"action_type": "push_notification", "content": "Urgent: review this now!"}),
                    "MODIFIED",
                    "Removed urgency framing to avoid manipulation pattern",
                    [],
                    ["manipulation_detector"],
                    0.87,
                ),
            ]
            for entry in esl_entries:
                cur.execute(
                    """
                    INSERT INTO public.esl_audit_log
                        (user_id, proposed_action, decision_status, decision_reason,
                         violated_values, applied_rules, confidence)
                    VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    entry,
                )
            logger.info("  inserted %d ESL audit entries", len(esl_entries))

    logger.info("Seed complete. Login: %s / dev123", DEV_EMAIL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        seed()
    except Exception:
        logger.exception("Seed failed")
        sys.exit(1)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend
pytest tests/test_seed_dev.py -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_dev.py backend/tests/test_seed_dev.py
git commit -m "feat: add seed_dev script for local dev database"
```

---

### Task 5: End-to-end smoke test

- [ ] **Step 1: Run the full test suite to confirm nothing broke**

```bash
make test
```

Expected: all backend tests pass (frontend tests pass or are skipped with `--passWithNoTests`).

- [ ] **Step 2: Run lint**

```bash
make lint
```

Expected: exits 0.

- [ ] **Step 3: Verify dry-run works via Make**

```bash
make migrate-dry
```

Expected: prints either "No pending migrations." or a list of pending `.sql` files with their content. No database changes.

- [ ] **Step 4: Final commit if any fixups were needed**

```bash
git add -p
git commit -m "chore: fixups from smoke test"
```

Only run this step if Step 1–3 required any fixes.
