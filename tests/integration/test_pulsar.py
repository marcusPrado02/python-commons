"""Integration tests for Apache Pulsar adapter (§57.6 / B-08).

Produce/consume round-trip against a real Pulsar container.
Run with: pytest tests/integration/test_pulsar.py -m integration -v

Requires Docker.  The Pulsar standalone container takes ~30-60s to start.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


_SERVICE_PORT = 6650


def _pulsar_service_url(container: Any) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(_SERVICE_PORT)
    return f"pulsar://{host}:{port}"


@pytest.fixture(scope="module")
def pulsar_url() -> str:  # type: ignore[return]
    container = (
        DockerContainer("apachepulsar/pulsar:3.2.4")
        .with_command("bin/pulsar standalone")
        .with_exposed_ports(_SERVICE_PORT)
    )
    with container as c:
        # Wait until Pulsar's broker is ready
        wait_for_logs(c, "messaging service is ready", timeout=120)
        time.sleep(5)  # extra buffer for the broker to accept connections
        yield _pulsar_service_url(c)


# ---------------------------------------------------------------------------
# §57.6 — PulsarProducer / PulsarConsumer
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPulsarIntegration:
    """Produce/consume round-trip against a real Pulsar container."""

    def test_produce_consume_round_trip(self, pulsar_url: str) -> None:
        pytest.importorskip("pulsar")
        from mp_commons.adapters.pulsar import PulsarConsumer, PulsarProducer
        from mp_commons.kernel.messaging import Message

        topic = "persistent://public/default/test-rt"
        subscription = "sub-rt"

        async def _run_test() -> None:
            async with PulsarProducer(pulsar_url) as producer:
                msg = Message(
                    topic=topic,
                    payload={"event": "order.created", "order_id": "ord-99"},
                )
                await producer.publish(msg)

            received: list[Any] = []
            consumer = PulsarConsumer(pulsar_url, topic=topic, subscription=subscription)
            async with consumer:
                async for raw_msg in consumer:
                    received.append(raw_msg)
                    await consumer.ack(raw_msg)
                    break  # only expect one message

            assert len(received) == 1

        _run(_run_test())
