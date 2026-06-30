"""Integration tests for Item CRUD endpoints.

Uses a real PostgreSQL testcontainer (session-scoped) via the test_client fixture.
Each test creates its own data; items persist for the session but tests are
independent because they use unique names and IDs.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


def test_create_item_returns_201(test_client: TestClient) -> None:
    response = test_client.post(
        "/api/v1/items/",
        json={"name": "Integration Item", "description": "created in test"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Integration Item"
    assert body["description"] == "created in test"
    assert uuid.UUID(body["id"])  # valid UUID


def test_get_item_returns_200(test_client: TestClient) -> None:
    created = test_client.post(
        "/api/v1/items/",
        json={"name": "Fetchable Item"},
    ).json()

    response = test_client.get(f"/api/v1/items/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_item_not_found_returns_404(test_client: TestClient) -> None:
    response = test_client.get(f"/api/v1/items/{uuid.uuid4()}")
    assert response.status_code == 404


def test_list_items_returns_paginated_response(test_client: TestClient) -> None:
    for i in range(3):
        test_client.post("/api/v1/items/", json={"name": f"List Test Item {i}"})

    response = test_client.get("/api/v1/items/?offset=0&limit=5")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert body["limit"] == 5
    assert body["offset"] == 0


def test_update_item_returns_updated_fields(test_client: TestClient) -> None:
    created = test_client.post(
        "/api/v1/items/",
        json={"name": "Before Update"},
    ).json()

    response = test_client.patch(
        f"/api/v1/items/{created['id']}",
        json={"name": "After Update"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "After Update"


def test_update_nonexistent_item_returns_404(test_client: TestClient) -> None:
    response = test_client.patch(
        f"/api/v1/items/{uuid.uuid4()}",
        json={"name": "Ghost"},
    )
    assert response.status_code == 404


def test_delete_item_returns_204(test_client: TestClient) -> None:
    created = test_client.post(
        "/api/v1/items/",
        json={"name": "To Be Deleted"},
    ).json()

    response = test_client.delete(f"/api/v1/items/{created['id']}")
    assert response.status_code == 204


def test_delete_then_get_returns_404(test_client: TestClient) -> None:
    created = test_client.post(
        "/api/v1/items/",
        json={"name": "Delete Then Get"},
    ).json()

    test_client.delete(f"/api/v1/items/{created['id']}")
    assert test_client.get(f"/api/v1/items/{created['id']}").status_code == 404


def test_list_limit_clamped_to_100(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/items/?limit=999")
    assert response.status_code == 422  # Pydantic validation rejects > 100
