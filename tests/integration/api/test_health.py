"""Integration tests for health endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_liveness(test_client: TestClient) -> None:
    response = test_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_200(redis_url: str, test_client: TestClient) -> None:
    """`/health/ready` checks both DB and Redis — needs the redis_url fixture
    so settings.redis_url points at a reachable container, not a guess."""
    response = test_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"
    assert data["redis"] == "ok"
