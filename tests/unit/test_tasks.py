"""Unit tests for background tasks.

ARQ tasks are plain async functions — testable without Redis or a running worker.
Pass an empty dict (or a mock) as `ctx`; ARQ only populates it during real execution.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.application.tasks.example import notify_example
from app.shared.correlation import get as get_correlation_id


async def test_notify_example_runs_without_error() -> None:
    await notify_example({}, resource_id="resource-uuid-1")


async def test_notify_example_restores_correlation_id_after_run() -> None:
    """Correlation ID ContextVar must be reset even if the task raises."""
    await notify_example({}, resource_id="abc", _correlation_id="cid-before")
    # After the task the ContextVar should be back to its default ("")
    assert get_correlation_id() == ""


async def test_notify_example_sets_correlation_id_during_execution() -> None:
    captured: list[str] = []

    original_logger_info = __import__("logging").getLogger(
        "app.application.tasks.example"
    ).info

    def capturing_info(msg: str, *args, **kwargs) -> None:
        captured.append(get_correlation_id())

    with patch(
        "app.application.tasks.example.logger.info",
        side_effect=capturing_info,
    ):
        await notify_example({}, resource_id="x", _correlation_id="req-cid-xyz")

    assert all(cid == "req-cid-xyz" for cid in captured), captured


async def test_notify_example_no_correlation_id_is_fine() -> None:
    """Calling without _correlation_id must not raise."""
    await notify_example({}, resource_id="no-cid-resource")
    assert get_correlation_id() == ""


async def test_notify_example_correlation_id_reset_on_exception() -> None:
    """ContextVar must be cleaned up even if the task body raises."""
    with patch(
        "app.application.tasks.example.logger.info",
        side_effect=[None, RuntimeError("task failed")],
    ):
        with pytest.raises(RuntimeError):
            await notify_example({}, resource_id="fail", _correlation_id="cid-fail")

    assert get_correlation_id() == ""
