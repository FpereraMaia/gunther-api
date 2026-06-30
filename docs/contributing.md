# Contributing

## Local setup

```bash
uv sync
pre-commit install   # installs git hooks
```

## Commit conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
The pre-commit hook enforces the format.

```
feat(auth): add JWT refresh token endpoint
fix(user): handle null email on registration
chore(deps): bump fastapi to 0.116
```

## Adding a feature

1. Create a branch: `git checkout -b feat/<name>`
2. Run tests: `make test`
3. Run linters: `make lint`
4. Commit with conventional format
5. Open a PR — CI runs full suite

## Adding a new domain

```bash
octopus scaffold domain gunther_api <domain_name>
```

This creates the domain, application, infrastructure, and presentation layers
with the standard structure.

## Creating a migration

```bash
# Make your model changes in infrastructure/database/<domain>/models.py
make migrate-create MSG="describe what changed"
make migrate          # apply locally
```

## Documentation

```bash
make docs-serve   # live preview at :8001
make docs-env     # regenerate configuration.md from .env.example
```

Documentation is deployed automatically on release via `mike`.
