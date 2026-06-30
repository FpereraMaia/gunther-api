"""ARQ background worker — process entrypoint.

Start locally:
    make worker
    # which runs: PYTHONPATH=src uv run arq app.worker.WorkerSettings

In Docker (worker service CMD):
    arq app.worker.WorkerSettings

How to enqueue a job from the web app or another task:

    from arq import create_pool
    from app.worker import WorkerSettings
    from app.shared.correlation import get as get_correlation_id

    redis = await create_pool(WorkerSettings.redis_settings)
    await redis.enqueue_job(
        "notify_example",
        resource_id=str(entity.id),
        _correlation_id=get_correlation_id(),  # threads the ID into the task log
    )

The _correlation_id convention: pass it as a kwarg to every enqueue_job() call so
that background task logs appear in the same Loki stream as the triggering request.
"""
from __future__ import annotations

import logging
from typing import Any

from arq.connections import RedisSettings

from app.application.tasks.example import notify_example
from app.shared.config import settings

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    """Called once when the worker process starts."""
    from app.infrastructure.telemetry.otel import setup_telemetry
    from app.infrastructure.telemetry.logging import setup_logging
    from app.infrastructure.telemetry.sentry import setup_sentry

    setup_telemetry(settings)
    setup_logging(settings)
    setup_sentry(settings)
    logger.info("worker.startup", extra={"service": settings.otel_service_name})


async def shutdown(ctx: dict[str, Any]) -> None:
    """Called once when the worker process stops."""
    logger.info("worker.shutdown", extra={"service": settings.otel_service_name})


class WorkerSettings:
    """ARQ WorkerSettings — discovered by `arq app.worker.WorkerSettings`.

    Add new task functions to `functions` as you create them in application/tasks/.
    """

    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    functions = [notify_example]

    on_startup = startup
    on_shutdown = shutdown

    queue_name = "gunther_api:default"
    max_jobs = 10
    job_timeout = 300   # seconds — raise for long-running tasks
    keep_result = 3600  # seconds to retain finished-job state in Redis
