"""Example background task — demonstrates the recommended pattern.

Copy this file as a template when adding new tasks:
  1. Define an async function with `ctx` + typed kwargs
  2. Add it to `WorkerSettings.functions` in src/app/worker.py
  3. Enqueue it from a use case or route handler:

        from arq import create_pool
        from app.worker import WorkerSettings
        from app.shared.correlation import get as get_correlation_id

        redis = await create_pool(WorkerSettings.redis_settings)
        await redis.enqueue_job(
            "notify_example",
            resource_id=str(entity.id),
            _correlation_id=get_correlation_id(),
        )

Correlation ID convention:
  Pass `_correlation_id` as a kwarg to every enqueue_job() call.
  The task restores it in the ContextVar so that all log lines emitted
  during the task execution carry the same ID as the triggering request.
"""
from __future__ import annotations

import logging
from typing import Any

from opentelemetry import trace

from app.shared.correlation import reset, set_id

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


async def notify_example(
    ctx: dict[str, Any],
    *,
    resource_id: str,
    _correlation_id: str = "",
) -> None:
    """
    Example task — replace the body with real business logic.

    Args:
        ctx:              ARQ worker context (holds redis pool, job_id, etc.)
        resource_id:      ID of the entity that triggered this task.
        _correlation_id:  Forwarded from the originating web request.
    """
    cid_token = set_id(_correlation_id) if _correlation_id else None
    with tracer.start_as_current_span("task.notify_example") as span:
        span.set_attribute("task.resource_id", resource_id)
        if _correlation_id:
            span.set_attribute("correlation.id", _correlation_id)
        try:
            logger.info(
                "task.notify_example.start",
                extra={"resource_id": resource_id},
            )

            # ── Business logic here ───────────────────────────────────────────
            # e.g. send an email, call an external API, update a read model
            # Raise an exception to trigger ARQ's built-in retry mechanism.
            # ─────────────────────────────────────────────────────────────────

            logger.info(
                "task.notify_example.complete",
                extra={"resource_id": resource_id},
            )
        finally:
            if cid_token is not None:
                reset(cid_token)
