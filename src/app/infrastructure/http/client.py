"""Inter-service HTTP client.

Features:
  Correlation ID  — X-Correlation-ID injected from the current request ContextVar
                    so the downstream service logs with the same ID.
  OTel tracing    — traceparent / tracestate headers are auto-injected by
                    HTTPXClientInstrumentor (wired in Phase 3). No duplication here.
  Retry           — transient errors (connection failures, timeouts, 5xx) are retried
                    with exponential backoff via Tenacity.
  Context manager — ServiceClient implements async context manager; also available
                    as a FastAPI dependency via get_http_client().

Usage:

    # As a context manager in a use case or background task:
    async with ServiceClient(base_url="http://other-service") as client:
        data = await client.get_json("/api/v1/resource")

    # As a FastAPI Depends():
    @router.get("/proxy")
    async def proxy(
        client: Annotated[ServiceClient, Depends(get_http_client("http://other-service"))]
    ) -> dict:
        return await client.get_json("/api/v1/resource")
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.shared.correlation import get as get_correlation_id

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(timeout=10.0, connect=5.0)
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_MIN_WAIT = 0.5   # seconds
DEFAULT_RETRY_MAX_WAIT = 10.0  # seconds


class _ServerError(Exception):
    """Raised internally to trigger Tenacity retry on 5xx responses."""

    def __init__(self, status_code: int, text: str) -> None:
        super().__init__(f"HTTP {status_code}: {text}")
        self.status_code = status_code


async def _inject_correlation_header(request: httpx.Request) -> None:
    """httpx request hook — injects X-Correlation-ID from the active ContextVar."""
    cid = get_correlation_id()
    if cid:
        request.headers["X-Correlation-ID"] = cid


class ServiceClient:
    """Async HTTP client for calling other Octopus services.

    OTel trace propagation (traceparent/tracestate) is handled automatically
    by HTTPXClientInstrumentor — this class only handles correlation ID and retry.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        retry_min_wait: float = DEFAULT_RETRY_MIN_WAIT,
        retry_max_wait: float = DEFAULT_RETRY_MAX_WAIT,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers=headers or {},
            event_hooks={"request": [_inject_correlation_header]},
        )
        self._retry_attempts = retry_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    # ── Public API ─────────────────────────────────────────────────────────────

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._request("DELETE", url, **kwargs)

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        """Convenience method — GET and return the parsed JSON body."""
        response = await self.get(url, **kwargs)
        response.raise_for_status()
        return response.json()

    async def post_json(self, url: str, **kwargs: Any) -> Any:
        """Convenience method — POST JSON and return the parsed JSON body."""
        response = await self.post(url, **kwargs)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()

    # ── Retry core ─────────────────────────────────────────────────────────────

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        _transient = (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError, _ServerError)
        last_response: httpx.Response | None = None

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._retry_attempts),
            wait=wait_exponential(
                multiplier=self._retry_min_wait,
                max=self._retry_max_wait,
            ),
            retry=retry_if_exception_type(_transient),
            reraise=True,
        ):
            with attempt:
                response = await self._client.request(method, url, **kwargs)
                last_response = response
                if response.status_code >= 500:
                    logger.warning(
                        "upstream.error",
                        extra={
                            "method": method,
                            "url": url,
                            "status": response.status_code,
                            "attempt": attempt.retry_state.attempt_number,
                        },
                    )
                    raise _ServerError(response.status_code, response.text[:200])

        assert last_response is not None  # always set — loop runs at least once
        return last_response

    # ── Context manager ────────────────────────────────────────────────────────

    async def __aenter__(self) -> ServiceClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()


def get_http_client(
    base_url: str,
    *,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
) -> Callable[[], AsyncIterator[ServiceClient]]:
    """
    FastAPI dependency factory for ServiceClient.

    Usage:
        OtherClient = Annotated[ServiceClient, Depends(get_http_client("http://other-svc"))]

        @router.get("/proxy")
        async def proxy(client: OtherClient) -> dict:
            return await client.get_json("/api/v1/items")
    """

    async def _dependency() -> AsyncIterator[ServiceClient]:
        async with ServiceClient(
            base_url=base_url,
            timeout=timeout,
            retry_attempts=retry_attempts,
        ) as client:
            yield client

    return _dependency
