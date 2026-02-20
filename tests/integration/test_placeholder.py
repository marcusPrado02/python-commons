"""Integration test placeholder — requires live services.

Run with:  pytest -m integration
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestRedisIntegration:
    """Placeholder — requires a running Redis instance."""

    @pytest.mark.skip(reason="Requires live Redis")
    async def test_rate_limiter_sliding_window(self) -> None:
        pass

    @pytest.mark.skip(reason="Requires live Redis")
    async def test_idempotency_store_ttl(self) -> None:
        pass


@pytest.mark.integration
class TestPostgresIntegration:
    """Placeholder — requires a running Postgres instance."""

    @pytest.mark.skip(reason="Requires live Postgres")
    async def test_outbox_round_trip(self) -> None:
        pass

    @pytest.mark.skip(reason="Requires live Postgres")
    async def test_unit_of_work_commit(self) -> None:
        pass


@pytest.mark.integration
class TestKafkaIntegration:
    """Placeholder — requires a running Kafka broker."""

    @pytest.mark.skip(reason="Requires live Kafka")
    async def test_produce_and_consume(self) -> None:
        pass
