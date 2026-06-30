#!/bin/sh
# Docker entrypoint — switches to debugpy mode when APP_DEBUG=true.
# Otherwise executes CMD as-is (uvicorn for app, arq for worker).
set -e

if [ "$APP_DEBUG" = "true" ]; then
    exec python -m debugpy \
        --listen 0.0.0.0:5678 \
        --wait-for-client \
        -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --reload-dir /app/src
fi

exec "$@"
