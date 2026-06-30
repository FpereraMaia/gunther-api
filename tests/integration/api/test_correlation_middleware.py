"""Integration tests for the CorrelationIDMiddleware."""
from __future__ import annotations

import re
import uuid

from fastapi.testclient import TestClient

UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def test_generates_correlation_id_when_absent(test_client: TestClient) -> None:
    response = test_client.get("/health/live")
    cid = response.headers.get("x-correlation-id")
    assert cid is not None, "X-Correlation-ID header must be present in response"
    assert UUID4_RE.match(cid), f"Expected UUID4, got: {cid}"


def test_echoes_client_correlation_id(test_client: TestClient) -> None:
    client_id = str(uuid.uuid4())
    response = test_client.get("/health/live", headers={"X-Correlation-ID": client_id})
    assert response.headers.get("x-correlation-id") == client_id


def test_different_requests_get_different_ids(test_client: TestClient) -> None:
    r1 = test_client.get("/health/live")
    r2 = test_client.get("/health/live")
    assert r1.headers["x-correlation-id"] != r2.headers["x-correlation-id"]
