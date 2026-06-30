"""Unit tests for the correlation ID ContextVar store."""

from __future__ import annotations

import uuid

from app.shared.correlation import generate, get, reset, set_id


def test_default_is_empty() -> None:
    assert get() == ""


def test_set_and_get() -> None:
    token = set_id("abc-123")
    try:
        assert get() == "abc-123"
    finally:
        reset(token)
    assert get() == ""


def test_generate_is_valid_uuid() -> None:
    cid = generate()
    parsed = uuid.UUID(cid)
    assert parsed.version == 4


def test_generate_is_unique() -> None:
    assert generate() != generate()
