"""Unit tests for ServiceClient — uses httpx.MockTransport (no extra deps)."""
from __future__ import annotations

import pytest
import httpx

from app.infrastructure.http.client import (
    ServiceClient,
    _ServerError,
    _inject_correlation_header,
)
from app.shared.correlation import reset, set_id


def _transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    it = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return next(it)

    return httpx.MockTransport(handler)


def _patched(client: ServiceClient, responses: list[httpx.Response]) -> ServiceClient:
    """Replace the internal httpx client with a mock-transport one."""
    client._client = httpx.AsyncClient(
        base_url="http://test",
        transport=_transport(responses),
    )
    return client


# ── Correlation ID hook ────────────────────────────────────────────────────────


async def test_correlation_id_header_injected() -> None:
    request = httpx.Request("GET", "http://test/api")
    token = set_id("cid-xyz")
    try:
        await _inject_correlation_header(request)
        assert request.headers["x-correlation-id"] == "cid-xyz"
    finally:
        reset(token)


async def test_correlation_id_omitted_when_empty() -> None:
    request = httpx.Request("GET", "http://test/api")
    await _inject_correlation_header(request)  # no set_id() — ContextVar default is ""
    assert "x-correlation-id" not in request.headers


# ── Happy path ─────────────────────────────────────────────────────────────────


async def test_get_returns_200_response() -> None:
    client = _patched(
        ServiceClient(base_url="http://test", retry_attempts=1),
        [httpx.Response(200, json={"id": 1})],
    )
    async with client:
        response = await client.get("/items/1")
    assert response.status_code == 200
    assert response.json() == {"id": 1}


async def test_get_json_returns_parsed_body() -> None:
    client = _patched(
        ServiceClient(base_url="http://test", retry_attempts=1),
        [httpx.Response(200, json={"name": "widget"})],
    )
    async with client:
        data = await client.get_json("/items/1")
    assert data == {"name": "widget"}


async def test_post_passes_json_body() -> None:
    client = _patched(
        ServiceClient(base_url="http://test", retry_attempts=1),
        [httpx.Response(201, json={"created": True})],
    )
    async with client:
        response = await client.post("/items", json={"name": "new"})
    assert response.status_code == 201


# ── Retry on 5xx ───────────────────────────────────────────────────────────────


async def test_retries_5xx_then_succeeds() -> None:
    client = _patched(
        ServiceClient(base_url="http://test", retry_attempts=3, retry_min_wait=0.0),
        [
            httpx.Response(503, text="unavailable"),
            httpx.Response(200, json={"ok": True}),
        ],
    )
    async with client:
        response = await client.get("/endpoint")
    assert response.status_code == 200


async def test_raises_server_error_after_max_retries() -> None:
    client = _patched(
        ServiceClient(base_url="http://test", retry_attempts=3, retry_min_wait=0.0),
        [httpx.Response(500, text="error")] * 3,
    )
    async with client:
        with pytest.raises(_ServerError):
            await client.get("/endpoint")


# ── 4xx is not retried ─────────────────────────────────────────────────────────


async def test_4xx_returned_without_retry() -> None:
    # Only one response in the list — if it retried, StopIteration would blow up.
    client = _patched(
        ServiceClient(base_url="http://test", retry_attempts=3, retry_min_wait=0.0),
        [httpx.Response(404, json={"detail": "not found"})],
    )
    async with client:
        response = await client.get("/missing")
    assert response.status_code == 404
