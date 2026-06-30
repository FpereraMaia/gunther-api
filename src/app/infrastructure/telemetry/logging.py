"""Structlog configuration — JSON with OTel trace correlation.

Every log line includes:
  timestamp, level, logger, service, env — always present
  trace_id, span_id — injected from active OTel span (when a request is in flight)
  correlation_id   — injected in Phase 4 (correlation ID middleware)

Logs go to stdout as JSON. In Docker, Alloy's docker log collector tails stdout
and forwards to Loki with service_name as a label.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.shared.config import Settings


def _add_service_context(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    from app.shared.config import settings as _settings

    event_dict["service"] = _settings.otel_service_name
    event_dict["env"] = _settings.otel_environment
    return event_dict


def _add_otel_context(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject trace_id and span_id from the active OTel span into every log line."""
    from opentelemetry import trace

    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def _add_correlation_id(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject correlation_id from the ContextVar set by CorrelationIDMiddleware."""
    from app.shared.correlation import get

    cid = get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


#: Processors shared between structlog and stdlib (for foreign log records)
_SHARED_PROCESSORS: list[Any] = [
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.ExceptionRenderer(),
    _add_service_context,
    _add_otel_context,
    _add_correlation_id,
]


def setup_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    structlog.configure(
        processors=_SHARED_PROCESSORS + [structlog.processors.JSONRenderer()],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog so third-party libraries also emit JSON
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
            foreign_pre_chain=_SHARED_PROCESSORS,
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Suppress high-frequency / low-value noise from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
