# ── Builder stage ──────────────────────────────────────────────────────────────
# Installs Python dependencies into an isolated venv.
# This layer is only rebuilt when pyproject.toml or uv.lock changes.
FROM python:3.12-slim AS builder

# Use /app as WORKDIR in both stages so venv shebangs point to /app/.venv/bin/python3
# which remains valid after copying into the runtime stage.
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Layer 1 — install deps only (cached unless pyproject.toml / uv.lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Layer 2 — install the project itself (invalidated when src/ changes)
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user — reduce blast radius if the container is compromised
RUN groupadd --system --gid 1001 app \
 && useradd  --system --uid 1001 --gid app --no-create-home app

WORKDIR /app

# Copy the venv from builder — shebangs already point to /app/.venv/bin/python3
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app src/        ./src/
COPY --chown=app:app alembic/    ./alembic/
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app entrypoint.sh ./entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app

EXPOSE 8000
# debugpy port — active only when APP_DEBUG=true (entrypoint switches to debugpy mode)
EXPOSE 5678

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

ENTRYPOINT ["/app/entrypoint.sh"]
# Override CMD in docker-compose for the worker service:
#   command: ["arq", "app.worker.WorkerSettings"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
