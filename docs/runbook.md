# Runbook

## Health checks

| Endpoint | Expected |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `GET /health/ready` | `{"status": "ok", "db": "ok", "redis": "ok"}` |

## Common incidents

### Service won't start

1. Check `.env` — `DATABASE_URL` must be reachable
2. Check migrations: `make migrate`
3. Check logs: `make logs`

### Database connection errors

```bash
make psql                 # verify DB is reachable
make migrate-history      # check current migration state
make migrate              # apply any pending migrations
```

### High error rate

1. Check Grafana → Tempo traces for slow/failing endpoints
2. Check Grafana → Loki for exception stack traces
3. Check Sentry for grouped errors

## Observability

| Tool | Platform URL | Standalone URL |
|---|---|---|
| Grafana | `http://grafana.localhost` | `http://localhost:3000` |
| Adminer | `http://adminer.localhost` | `http://localhost:8082` |

## Restart the service

```bash
# Platform-connected
octopus restart gunther_api

# Standalone
make docker-restart
```
