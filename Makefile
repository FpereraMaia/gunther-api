.DEFAULT_GOAL := help
SHELL         := bash

SERVICE  := gunther_api
COMPOSE  := docker compose
COMPOSE_SA := docker compose -f docker-compose.yml -f docker-compose.standalone.yml

.PHONY: help install dev dev-full debug worker \
        test test-cov test-file lint format \
        migrate migrate-create migrate-down migrate-history seed psql psql-standalone \
        docker-up docker-down docker-restart logs \
        schema-export docs docs-serve docs-env docs-deploy \
        ci-local clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' | sort

# ── Dev ───────────────────────────────────────────────────────────────────────

install: ## Install dependencies, pre-commit hooks, and git hooks
	uv sync
	git config --unset-all core.hooksPath || true
	uv run pre-commit install
	cp .github/hooks/post-merge .git/hooks/post-merge
	chmod +x .git/hooks/post-merge

dev: ## Hot-reload API locally — breakpoints work in VS Code without Docker
	PYTHONPATH=src uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src

dev-full: ## API + worker together via honcho (one terminal, reads Procfile)
	uv run honcho start

debug: ## Start app container with debugpy — attach "Attach — Docker" in VS Code
	APP_DEBUG=true $(COMPOSE) up app

worker: ## Run ARQ background worker locally
	PYTHONPATH=src uv run arq app.worker.WorkerSettings

# ── Test ──────────────────────────────────────────────────────────────────────

test: ## Run full test suite
	uv run pytest tests/ -v

test-cov: ## Run tests with coverage report (fails below 80%)
	uv run pytest tests/ -v --cov=app --cov-report=term-missing

test-file: ## Run a single test file: make test-file FILE=tests/unit/test_foo.py
	uv run pytest $(FILE) -v -x

# ── Code quality ──────────────────────────────────────────────────────────────

lint: ## Run ruff, mypy, bandit, semgrep
	uv run ruff check src/ tests/
	uv run mypy src/
	uv run bandit -c pyproject.toml -r src/ -q
	uv run semgrep scan --config=p/python --config=p/security-audit --error src/

format: ## Auto-format and fix imports (ruff)
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

# ── Database ──────────────────────────────────────────────────────────────────

migrate: ## Apply pending Alembic migrations
	PYTHONPATH=src uv run alembic upgrade head

migrate-create: ## Create migration: make migrate-create MSG="add users table"
	PYTHONPATH=src uv run alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Roll back the last migration
	PYTHONPATH=src uv run alembic downgrade -1

migrate-history: ## Show migration history
	PYTHONPATH=src uv run alembic history --verbose

seed: ## Seed development data
	PYTHONPATH=src uv run python -m scripts.seed

psql: ## Open psql (platform-connected mode — uses octopus-postgres)
	docker exec -it octopus-postgres psql -U octopus -d gunther_api_db

psql-standalone: ## Open psql (standalone mode — uses local postgres container)
	$(COMPOSE_SA) exec postgres psql -U postgres -d gunther_api_db

# ── Docker ────────────────────────────────────────────────────────────────────

docker-up: ## Start standalone stack (postgres, redis, observability) and run migrations
	$(COMPOSE_SA) up -d
	@echo "Waiting for Postgres to be ready..."
	@sleep 3
	$(MAKE) migrate
	@echo ""
	@echo "  App:     http://localhost:8000"
	@echo "  Swagger: http://localhost:8000/docs"
	@echo "  Grafana: http://localhost:3000"
	@echo "  Adminer: http://localhost:8082"

docker-down: ## Stop standalone stack (data is preserved in named volumes)
	$(COMPOSE_SA) down

docker-restart: ## Restart app container only
	$(COMPOSE) restart app

logs: ## Tail app container logs
	$(COMPOSE) logs -f app

# ── Schema ────────────────────────────────────────────────────────────────────

schema-export: ## Export OpenAPI schema to openapi.json
	@PYTHONPATH=src uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))" > openapi.json
	@echo "Exported to openapi.json"

# ── Docs ──────────────────────────────────────────────────────────────────────

docs: docs-env ## Build MkDocs site → site/
	uv run mkdocs build

docs-serve: ## Live-reload docs at http://localhost:8001
	uv run mkdocs serve -a localhost:8001

docs-env: ## Regenerate docs/configuration.md from .env.example
	PYTHONPATH=src uv run python scripts/gen_docs_env.py

docs-deploy: ## Deploy versioned docs to GitHub Pages (called by release.yml with VERSION=x.y.z)
	uv run mike deploy --push --update-aliases $(VERSION) latest

# ── CI ────────────────────────────────────────────────────────────────────────

ci-local: ## Run full CI pipeline locally using act
	act push --rm

# ── Reset ─────────────────────────────────────────────────────────────────────

clean: ## DESTRUCTIVE: stop standalone stack and delete all volumes (resets database + cache)
	@echo ""
	@echo "  WARNING: This deletes all local data for $(SERVICE)."
	@echo "  For platform-connected mode use: octopus down --purge $(SERVICE)"
	@echo ""
	@read -p "  Type '$(SERVICE)' to confirm: " confirm && [ "$$confirm" = "$(SERVICE)" ] || exit 1
	$(COMPOSE_SA) down -v
	@echo "  Done. Run 'make docker-up' to start fresh."
