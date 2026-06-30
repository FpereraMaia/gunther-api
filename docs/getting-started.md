# Getting Started

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine
- [Octopus CLI](https://github.com//octopus) — for platform-connected mode
- VS Code with the [recommended extensions](../.vscode/extensions.json)

## Platform-connected mode (recommended)

Use this when running Gunther API alongside other Octopus services.

```bash
octopus platform up                  # start shared Postgres, Redis, Grafana, Traefik
octopus up gunther_api           # provision DB, write .env, run migrations
make install                         # uv sync
make dev                             # hot-reload API at gunther_api.localhost
```

## Standalone mode

Use this when you want to run the service in complete isolation.

```bash
cp .env.example .env                 # fill in secrets
make install                         # uv sync
make docker-up                       # start postgres, redis, observability stack
```

The app will be available at `http://localhost:8000`.

## VS Code debug setup

After `make dev` or `make docker-up`, open VS Code and press **F5** to launch with the
`API — uvicorn (hot reload)` config. Breakpoints work immediately — no attach step needed.

To debug a Docker container: run `make debug`, then use the `Attach — Docker container`
launch config in VS Code.

## Running tests

```bash
make test           # full suite
make test-cov       # with coverage report
```

Tests use `testcontainers` for Postgres — no running database required.

## First domain

After setup, scaffold your first business domain:

```bash
octopus scaffold domain gunther_api <domain_name>
```
