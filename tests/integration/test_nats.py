"""Integration tests for NATS adapter (§30.3).

Uses testcontainers to spawn a real NATS server.
Run with: PYTHONPATH=src pytest tests/integration/test_nats.py -m integration -v

Note: NatsMessageBus uses JetStream publish.  The container must have
JetStream enabled (NATS ≥ 2.2; the default testcontainers image supports it).
"""
from __future__ import annotations

import asyncio

import pytest
from testcontainers.nats import NatsContainer

from mp_commons.adapters.nats import NatsMessageBus
from mp_commons.kernel.messaging import Message, MessageHeaders


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# §30.3 – NatsMessageBus
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestNatsMessageBusIntegration:
    """Real NATS JetStream publish tests."""

    def test_connect_and_close(self) -> None:
        with NatsContainer(jetstream=True) as container:
            url = container.nats_uri()

            async def run() -> None:
                bus = NatsMessageBus(servers=url)
                await bus.connect()
                await bus.close()

            _run(run())

    def test_context_manager_connect_close(self) -> None:
        with NatsContainer(jetstream=True) as container:
            url = container.nats_uri()

            async def run() -> None:
                async with NatsMessageBus(servers=url):
                    pass  # connect / close without error

            _run(run())

    def test_publish_single_message(self) -> None:
        with NatsContainer(jetstream=True) as container:
            url = container.nats_uri()

            async def run() -> None:
                import nats  # type: ignore[import-untyped]

                msg = Message(
                    id="nats-1",
                    topic="orders.placed",
                    payload={"order_id": "101"},
                    headers=MessageHeaders(),
                )

                nc = await nats.connect(url)
                js = nc.jetstream()
                # Create stream so JetStream publish succeeds
                await js.add_stream(name="orders", subjects=["orders.*"])
                await nc.close()

                async with NatsMessageBus(servers=url) as bus:
                    await bus.publish(msg)  # should not raise

            _run(run())

    def test_publish_batch(self) -> None:
        with NatsContainer(jetstream=True) as container:
            url = container.nats_uri()

            async def run() -> None:
                import nats  # type: ignore[import-untyped]

                nc = await nats.connect(url)
                js = nc.jetstream()
                await js.add_stream(name="events", subjects=["events.*"])
                await nc.close()

                messages = [
                    Message(
                        id=f"batch-{i}",
                        topic="events.test",
                        payload={"seq": i},
                        headers=MessageHeaders(),
                    )
                    for i in range(3)
                ]

                async with NatsMessageBus(servers=url) as bus:
                    await bus.publish_batch(messages)  # should not raise

            _run(run())

    def test_publish_without_explicit_connect_auto_connects(self) -> None:
        with NatsContainer(jetstream=True) as container:
            url = container.nats_uri()

            async def run() -> None:
                import nats  # type: ignore[import-untyped]

                nc = await nats.connect(url)
                js = nc.jetstream()
                await js.add_stream(name="auto", subjects=["auto.*"])
                await nc.close()

                bus = NatsMessageBus(servers=url)
                msg = Message(
                    id="auto-1",
                    topic="auto.connect",
                    payload={"x": 1},
                    headers=MessageHeaders(),
                )
                # publish() calls connect() internally if not connected
                await bus.publish(msg)
                await bus.close()

            _run(run())
