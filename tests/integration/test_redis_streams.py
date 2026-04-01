"""Integration tests for Redis Streams adapter (§56.6 / B-07).

Produce/consume round-trip, consumer group ACK, and pending entry list.
Run with: pytest tests/integration/test_redis_streams.py -m integration -v

Requires Docker.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from testcontainers.redis import RedisContainer


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def redis_url() -> str:  # type: ignore[return]
    with RedisContainer("redis:7-alpine") as rc:
        host = rc.get_container_host_ip()
        port = rc.get_exposed_port(rc.port)
        yield f"redis://{host}:{port}/0"


# ---------------------------------------------------------------------------
# §56.6 — RedisStreamProducer / RedisStreamConsumerGroup
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRedisStreamsIntegration:
    """Full round-trip tests against a real Redis container."""

    def _make_redis(self, redis_url: str) -> Any:
        import redis.asyncio as aioredis

        return aioredis.from_url(redis_url, decode_responses=False)

    def test_produce_consume_round_trip(self, redis_url: str) -> None:
        from mp_commons.adapters.redis.streams import (
            RedisStreamConsumerGroup,
            RedisStreamProducer,
        )

        async def _run_test() -> None:
            r = self._make_redis(redis_url)
            producer = RedisStreamProducer(r)
            consumer = RedisStreamConsumerGroup(r)

            stream = "test:roundtrip"
            group = "grp-rt"
            await consumer.create_group(stream, group, start_id="0")

            entry_id = await producer.publish(stream, {"event": "created", "order_id": "ord-1"})
            assert entry_id  # returns the stream entry ID

            entries = await consumer.read(stream, group, consumer="worker-1", count=10)
            assert len(entries) == 1
            assert entries[0].field_str("event") == "created"
            assert entries[0].field_str("order_id") == "ord-1"

            await r.aclose()

        _run(_run_test())

    def test_consumer_group_ack_removes_from_pel(self, redis_url: str) -> None:
        from mp_commons.adapters.redis.streams import (
            RedisStreamConsumerGroup,
            RedisStreamProducer,
        )

        async def _run_test() -> None:
            r = self._make_redis(redis_url)
            producer = RedisStreamProducer(r)
            consumer = RedisStreamConsumerGroup(r)

            stream = "test:ack"
            group = "grp-ack"
            await consumer.create_group(stream, group, start_id="0")

            await producer.publish(stream, {"msg": "ack-me"})

            entries = await consumer.read(stream, group, consumer="worker-1", count=5)
            assert len(entries) >= 1

            # ACK removes the entry from the Pending Entry List (PEL)
            acked = await consumer.ack(stream, group, *[e.id for e in entries])
            assert acked == len(entries)

            # Pending entries should now be empty for this consumer
            pending = await r.xpending_range(stream, group, "-", "+", 100)
            assert len(pending) == 0

            await r.aclose()

        _run(_run_test())

    def test_pending_entry_list_before_ack(self, redis_url: str) -> None:
        from mp_commons.adapters.redis.streams import (
            RedisStreamConsumerGroup,
            RedisStreamProducer,
        )

        async def _run_test() -> None:
            r = self._make_redis(redis_url)
            producer = RedisStreamProducer(r)
            consumer = RedisStreamConsumerGroup(r)

            stream = "test:pending"
            group = "grp-pending"
            await consumer.create_group(stream, group, start_id="0")

            await producer.publish(stream, {"msg": "not-yet-acked"})

            entries = await consumer.read(stream, group, consumer="worker-pend", count=5)
            assert len(entries) >= 1

            # Before ACK, entry is in the PEL
            pending = await r.xpending_range(stream, group, "-", "+", 100)
            assert len(pending) >= 1

            await r.aclose()

        _run(_run_test())
