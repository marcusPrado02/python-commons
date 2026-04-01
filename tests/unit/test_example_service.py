"""Smoke tests for the simple_service example (D-01)."""
from __future__ import annotations

import pytest


@pytest.fixture()
def client():
    # Import inside fixture — avoids requiring fastapi at collection time.
    # starlette.testclient correctly drives the ASGI lifespan protocol so
    # the app's startup handler runs before tests interact with it.
    pytest.importorskip("fastapi")
    from starlette.testclient import TestClient

    from examples.simple_service.app import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_liveness(client):
    resp = client.get("/health/live")
    assert resp.status_code == 200


def test_readiness(client):
    resp = client.get("/health/ready")
    assert resp.status_code == 200


def test_create_order_returns_201(client):
    resp = client.post(
        "/orders",
        json={"customer_id": "cust-1", "item_sku": "SKU-99", "quantity": 3},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["customer_id"] == "cust-1"
    assert body["item_sku"] == "SKU-99"
    assert body["quantity"] == 3
    assert "order_id" in body


def test_get_order_returns_created_order(client):
    created = client.post(
        "/orders",
        json={"customer_id": "cust-2", "item_sku": "SKU-10", "quantity": 1},
    )
    order_id = created.json()["order_id"]
    fetched = client.get(f"/orders/{order_id}")
    assert fetched.status_code == 200
    assert fetched.json()["order_id"] == order_id


def test_get_unknown_order_returns_404(client):
    resp = client.get("/orders/does-not-exist")
    assert resp.status_code == 404


def test_create_order_missing_field_returns_422(client):
    resp = client.post(
        "/orders",
        json={"customer_id": "cust-3"},  # missing item_sku and quantity
    )
    assert resp.status_code == 422
