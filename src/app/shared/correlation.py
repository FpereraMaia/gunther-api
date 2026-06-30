"""Correlation ID — async-safe ContextVar storage.

The middleware writes here on every incoming request.
The structlog processor in logging.py reads from here to inject
correlation_id into every log line emitted during request handling.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar, Token

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def get() -> str:
    return _correlation_id.get()


def set_id(value: str) -> Token[str]:  # noqa: A001
    return _correlation_id.set(value)


def reset(token: Token[str]) -> None:
    _correlation_id.reset(token)


def generate() -> str:
    return str(uuid.uuid4())
