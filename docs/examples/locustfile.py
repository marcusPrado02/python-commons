"""§47.6 — Locust load-test: realistic microservice traffic mix.

Simulates an 80 % read / 20 % write traffic pattern against a generic
REST microservice.  Designed to be dropped next to any FastAPI/ASGI app
that follows the standard mp-commons REST conventions.

Run with::

    pip install locust
    locust -f docs/examples/locustfile.py --host=http://localhost:8000

Tune ``READ_WEIGHT`` / ``WRITE_WEIGHT`` and ``TOTAL_USERS`` for your
target SLO:

    locust -f docs/examples/locustfile.py \\
        --host=http://localhost:8000 \\
        --users=100 --spawn-rate=10 \\
        --run-time=60s --headless

Endpoints assumed
-----------------
GET  /health              — liveness probe (not counted in mix)
GET  /api/orders          — list orders (read)
GET  /api/orders/{id}     — get order by id (read)
POST /api/orders          — create order (write)
PUT  /api/orders/{id}     — update order (write)

All IDs use UUID v4 to avoid caching artefacts.

Metrics to watch
----------------
- p50, p95, p99 latency per endpoint
- Requests/second (RPS) at target concurrency
- Error rate < 0.1 %
"""

from __future__ import annotations

import random
import uuid

try:
    from locust import HttpUser, between, task
except ImportError as exc:
    raise SystemExit(
        "locust is not installed.  Install it with:  pip install locust"
    ) from exc


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

READ_WEIGHT = 8   # 80 % of tasks
WRITE_WEIGHT = 2  # 20 % of tasks

# A small pool of pre-seeded UUIDs to keep "get by id" calls realistic
_ID_POOL: list[str] = [str(uuid.uuid4()) for _ in range(200)]


def _random_id() -> str:
    return random.choice(_ID_POOL)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# User behaviour
# ---------------------------------------------------------------------------


class MicroserviceUser(HttpUser):
    """Simulates a user hitting a microservice REST API.

    Wait between 50 ms and 500 ms between consecutive requests to model
    realistic think time.
    """

    wait_time = between(0.05, 0.5)

    # ------------------------------------------------------------------
    # Reads (80 %)
    # ------------------------------------------------------------------

    @task(READ_WEIGHT)
    def list_orders(self) -> None:
        """GET /api/orders — paginated list."""
        page = random.randint(1, 10)
        with self.client.get(
            f"/api/orders?page={page}&size=20",
            name="/api/orders [list]",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 404):
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(READ_WEIGHT)
    def get_order_by_id(self) -> None:
        """GET /api/orders/{id} — single resource fetch."""
        order_id = _random_id()
        with self.client.get(
            f"/api/orders/{order_id}",
            name="/api/orders/{id} [get]",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 404):
                resp.failure(f"Unexpected status: {resp.status_code}")

    # ------------------------------------------------------------------
    # Writes (20 %)
    # ------------------------------------------------------------------

    @task(WRITE_WEIGHT)
    def create_order(self) -> None:
        """POST /api/orders — create a new order."""
        payload = {
            "id": _new_id(),
            "customer_id": _random_id(),
            "items": [
                {"product_id": _random_id(), "quantity": random.randint(1, 5)}
                for _ in range(random.randint(1, 3))
            ],
        }
        with self.client.post(
            "/api/orders",
            json=payload,
            name="/api/orders [create]",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 201, 202, 422):
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(WRITE_WEIGHT)
    def update_order(self) -> None:
        """PUT /api/orders/{id} — update an existing order (idempotent)."""
        order_id = _random_id()
        payload = {"status": random.choice(["pending", "confirmed", "shipped"])}
        with self.client.put(
            f"/api/orders/{order_id}",
            json=payload,
            name="/api/orders/{id} [update]",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 204, 404, 422):
                resp.failure(f"Unexpected status: {resp.status_code}")

    # ------------------------------------------------------------------
    # Health check — always runs, not counted in the traffic mix
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        """Probe /health before the test starts; abort if unavailable."""
        resp = self.client.get("/health", name="/health [probe]")
        if resp.status_code not in (200, 204):
            self.environment.runner.quit()
