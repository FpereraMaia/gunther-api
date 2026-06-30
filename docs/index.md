# Gunther API

test

## Overview

This service is built on the [Octopus](https://github.com//octopus)
boilerplate stack:

- **FastAPI** — async HTTP API
- **SQLAlchemy async** — database ORM with Alembic migrations
- **Clean Architecture** — Domain → Application → Infrastructure → Presentation
- **Grafana OSS stack** — traces (Tempo), logs (Loki), metrics (Prometheus)
- **OpenTelemetry** — instrumentation for traces, logs, and metrics

## Quick Links

- [Getting Started](getting-started.md) — set up local dev in under 5 minutes
- [Architecture](architecture.md) — layer diagram and conventions
- [Configuration](configuration.md) — all environment variables
- [API](api.md) — Swagger UI and OpenAPI schema
- [Runbook](runbook.md) — health checks and incident procedures
