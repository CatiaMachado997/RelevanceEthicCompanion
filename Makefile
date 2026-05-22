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
