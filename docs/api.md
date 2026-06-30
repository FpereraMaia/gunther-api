# API Reference

## Interactive docs

| Mode | URL |
|---|---|
| Platform-connected | `http://gunther_api.localhost/docs` |
| Standalone | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |

## Export OpenAPI schema

```bash
make schema-export   # writes openapi.json
```

## Versioning

All endpoints are versioned under `/api/v1/`. Breaking changes increment the major version.

## Authentication


The API uses **JWT Bearer** authentication.

Obtain a token via `POST /api/v1/auth/login`, then pass it in subsequent requests:

```
Authorization: Bearer <token>
```

Tokens expire after `JWT_EXPIRE_MINUTES` (default 60 minutes).

