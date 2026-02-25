"""Integration tests for RabbitMQ adapter (§31.3).

Uses testcontainers to spawn a real RabbitMQ broker.
Run with: PYTHONPATH=src pytest tests/integration/test_rabbitmq.py -m integration -v
"""
from __future__ import annotations

import asyncio

import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from mp_commons.adapters.rabbitmq import RabbitMQMessageBus
from mp_commons.kernel.messaging import Message, MessageHeaders


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def _amqp_url(container: RabbitMqContainer) -> str:
    """Return the amqp:// URL for the container."""
    host = container.get_container_host_ip()
    port = container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


# ---------------------------------------------------------------------------
# §31.3 – RabbitMQMessageBus
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRabbitMQMessageBusIntegration:
    """Real RabbitMQ publish tests."""

    def test_connect_and_close(self) -> None:
        with RabbitMqContainer() as container:
            url = _amqp_url(container)

            async def run() -> None:
                bus = RabbitMQMessageBus(url=url)
                await bus.connect()
                await bus.close()

            _run(run())

    def test_context_manager_connect_close(self) -> None:
        with RabbitMqContainer() as container:
            url = _amqp_url(container)

            async def run() -> None:
                async with RabbitMQMessageBus(url=url):
                    pass  # connect / close without error

            _run(run())

    def test_publish_single_message(self) -> None:
        with RabbitMqContainer() as container:
            url = _amqp_url(container)

            async def run() -> None:
                import aio_pika  # type: ignore[import-untyped]

                # Declare queue so publish via default exchange works
                conn = await aio_pika.connect_robust(url)
                ch = await conn.channel()
                await ch.declare_queue("orders.placed", durable=False)
                await conn.close()

                msg = Message(
                    id="rmq-1",
                    topic="orders.placed",
                    payload={"order_id": "99"},
                    headers=MessageHeaders(),
                )
                async with RabbitMQMessageBus(url=url) as bus:
                    await bus.publish(msg)  # should not raise

            _run(run())

    def test_publish_batch(self) -> None:
        with RabbitMqContainer() as container:
            url = _amqp_url(container)

            async def run() -> None:
                import aio_pika  # type: ignore[import-untyped]

                conn = await aio_pika.connect_robust(url)
                ch = await conn.channel()
                await ch.declare_queue("events.test", durable=False)
                await conn.close()

                messages = [
                    Message(
                        id=f"rmq-batch-{i}",
                        topic="events.test",
                        payload={"seq": i},
                        headers=MessageHeaders(),
                    )
                    for i in range(3)
                ]
                async with RabbitMQMessageBus(url=url) as bus:
                    await bus.publish_batch(messages)  # should not raise

            _run(run())

    def test_publish_consume_roundtrip(self) -> None:
        with RabbitMqContainer() as container:
            url = _amqp_url(container)

            received: list[bytes] = []

            async def run() -> None:
                import aio_pika  # type: ignore[import-untyped]

                queue_name = "rt.queue"
                conn = await aio_pika.connect_robust(url)
                ch = await conn.channel()
                queue = await ch.declare_queue(queue_name, durable=False)

                msg = Message(
                    id="rmq-rt-1",
                    topic=queue_name,
                    payload={"hello": "world"},
                    headers=MessageHeaders(),
                )
                async with RabbitMQMessageBus(url=url) as bus:
                    await bus.publish(msg)

                # Consume one message
                amqp_msg = await queue.get(timeout=5, fail=False)
                if amqp_msg is not None:
                    received.append(amqp_msg.body)
                    await amqp_msg.ack()

                await conn.close()

            _run(run())
            assert len(received) == 1
            assert b"hello" in received[0]

    def test_publish_without_explicit_connect_auto_connects(self) -> None:
        with RabbitMqContainer() as container:
            url = _amqp_url(container)

            async def run() -> None:
                import aio_pika  # type: ignore[import-untyped]

                conn = await aio_pika.connect_robust(url)
                ch = await conn.channel()
                await ch.declare_queue("auto.q", durable=False)
                await conn.close()

                bus = RabbitMQMessageBus(url=url)
                msg = Message(
                    id="rmq-auto-1",
                    topic="auto.q",
                    payload={"auto": True},
                    headers=MessageHeaders(),
                )
                await bus.publish(msg)  # auto-connects internally
                await bus.close()

            _run(run())
