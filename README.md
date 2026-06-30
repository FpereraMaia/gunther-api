# Gunther API

test

Built with [Octopus](https://github.com//octopus) · FastAPI · Clean Architecture · Full observability

---

## Quick start

```bash
# Platform-connected (recommended)
octopus platform up
octopus up gunther_api
make dev

# Standalone (no platform)
make docker-up
make dev
```

Open:
- **Swagger UI**: http://localhost:8000/docs (standalone) · http://gunther_api.localhost/docs (platform)
- **Grafana**: http://localhost:3000 (standalone) · http://grafana.localhost (platform)

## Development

```bash
make install        # install dependencies
make dev            # hot-reload API (breakpoints work out of the box in VS Code)
make dev-full       # API + worker together (honcho)
make test           # run tests
make test-cov       # tests with coverage report
make lint           # ruff + mypy + bandit + semgrep
make migrate        # apply DB migrations
make docs-serve     # live docs at :8001
```

See `make help` for all available targets.

## Architecture

```
src/app/
├── domain/           # Entities, value objects, repository interfaces
├── application/      # Use cases — orchestrate domain logic
├── infrastructure/   # DB, cache, external clients
└── presentation/     # FastAPI routers, schemas, middleware
```

See [docs/architecture.md](docs/architecture.md) for the full diagram.

## Configuration

All config is environment-variable-driven via Pydantic Settings.
Copy `.env.example` to `.env` and fill in the required values.

See [docs/configuration.md](docs/configuration.md) for the full reference.

## Docs

```bash
make docs-serve   # live-reload at http://localhost:8001
make docs         # build static site → site/
```
