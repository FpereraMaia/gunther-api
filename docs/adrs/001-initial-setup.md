# ADR-001: Initial Project Setup

| Key | Value |
|---|---|
| **Date** | 2026-06-30 |
| **Status** | Accepted |
| **Author** |  |

## Context

This service was scaffolded by Octopus CLI using the `python-web` boilerplate.
The following feature flags were chosen at creation time.

## Decisions

### Language and runtime

- **Python 3.12** — minimum supported version
- **uv** — package and virtualenv manager

### Framework

- **FastAPI** — async HTTP API with native OpenAPI support
- **SQLAlchemy 2 async** — ORM, async sessions
- **Alembic** — schema migrations

### Architecture

- **Clean Architecture** — Domain → Application → Infrastructure → Presentation
- Dependencies point inward; domain layer has no external dependencies

### Features enabled at scaffold time

| Feature | Enabled |
|---|---|
| Redis cache + rate limiting | `y` |
| ARQ background worker | `y` |
| JWT Bearer auth | `y` |

### Observability

- **Grafana Alloy** — OTel collector
- **Grafana Tempo** — distributed tracing
- **Grafana Loki** — log aggregation
- **Prometheus + Grafana** — metrics and dashboards
- **Sentry** — runtime error monitoring (optional, configure `SENTRY_DSN`)

### Developer experience

- `make dev` — hot-reload local API with VS Code breakpoints
- `make dev-full` — API + worker via honcho
- `.vscode/launch.json` — 5 debug configs + API+Worker compound
- pre-commit: ruff, mypy, bandit, semgrep, commitizen, detect-secrets

## Consequences

All future ADRs for this service should be placed in `docs/adrs/` and numbered sequentially.
