"""Apache Pulsar adapter — producer, consumer, and outbox dispatcher.

Requires ``pulsar-client>=3.4``.  All classes raise :class:`ImportError` when
the library is absent.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mp_commons.kernel.messaging.message import Message


def _require_pulsar() -> Any:
    try:
        import pulsar  # type: ignore[import-untyped]

        return pulsar
    except ImportError as exc:
        raise ImportError(
            "pulsar-client is required for Pulsar adapters. "
            "Install it with: pip install 'pulsar-client>=3.4'"
        ) from exc


# ---------------------------------------------------------------------------
# Producer
# ---------------------------------------------------------------------------


class PulsarProducer:
    """Publish :class:`~mp_commons.kernel.messaging.message.Message` objects to Pulsar topics.

    Parameters
    ----------
    service_url:
        Pulsar service URL, e.g. ``pulsar://localhost:6650``.
    **client_kwargs:
        Extra kwargs forwarded to :class:`pulsar.Client`.
    """

    def __init__(self, service_url: str, **client_kwargs: Any) -> None:
        _require_pulsar()
        self._service_url = service_url
        self._client_kwargs = client_kwargs
        self._client: Any = None
        self._producers: dict[str, Any] = {}

    async def connect(self, service_url: str | None = None) -> None:
        """Connect to the Pulsar broker.

        *service_url* overrides the value passed at construction time.
        """
        import pulsar  # type: ignore[import-untyped]

        url = service_url or self._service_url
        loop = asyncio.get_event_loop()
        self._client = await loop.run_in_executor(
            None,
            lambda: pulsar.Client(url, **self._client_kwargs),
        )

    def _get_producer(self, topic: str) -> Any:
        if topic not in self._producers:
            self._producers[topic] = self._client.create_producer(topic)
        return self._producers[topic]

    async def publish(self, message: Message) -> None:
        """Serialize and publish *message* to its topic."""
        if self._client is None:
            await self.connect()

        payload = json.dumps(
            {
                "id": str(message.id),
                "type": type(message).__name__,
                "correlation_id": getattr(message.headers, "correlation_id", None),
                "payload": message.payload if isinstance(message.payload, dict) else {},
            }
        ).encode("utf-8")

        topic = getattr(message, "topic", type(message).__name__)
        producer = self._get_producer(topic)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, producer.send, payload)

    def close(self) -> None:
        """Close all producers and the client."""
        for producer in self._producers.values():
            try:
                producer.flush()
                producer.close()
            except Exception:
                pass
        self._producers.clear()
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    async def __aenter__(self) -> PulsarProducer:
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Consumer
# ---------------------------------------------------------------------------


class PulsarConsumer:
    """Async iterator over messages from a Pulsar topic subscription.

    Parameters
    ----------
    service_url:
        Pulsar service URL.
    topic:
        Topic to subscribe to.
    subscription:
        Subscription name.
    """

    def __init__(self, service_url: str, topic: str, subscription: str) -> None:
        _require_pulsar()
        self._service_url = service_url
        self._topic = topic
        self._subscription = subscription
        self._client: Any = None
        self._consumer: Any = None

    async def connect(
        self,
        service_url: str | None = None,
        topic: str | None = None,
        subscription: str | None = None,
    ) -> None:
        import pulsar  # type: ignore[import-untyped]

        url = service_url or self._service_url
        t = topic or self._topic
        s = subscription or self._subscription
        loop = asyncio.get_event_loop()
        self._client = await loop.run_in_executor(None, lambda: pulsar.Client(url))
        self._consumer = await loop.run_in_executor(
            None,
            lambda: self._client.subscribe(t, subscription_name=s),
        )

    def close(self) -> None:
        if self._consumer is not None:
            try:
                self._consumer.close()
            except Exception:
                pass
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass

    async def ack(self, msg: Any) -> None:
        """Acknowledge a raw Pulsar message."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._consumer.acknowledge, msg)

    def __aiter__(self) -> PulsarConsumer:
        return self

    async def __anext__(self) -> Any:
        """Yield the next raw Pulsar message."""
        if self._consumer is None:
            raise StopAsyncIteration
        loop = asyncio.get_event_loop()
        try:
            msg = await loop.run_in_executor(
                None,
                lambda: self._consumer.receive(timeout_millis=100),
            )
            return msg
        except Exception as exc:
            if "Timeout" in type(exc).__name__ or "timeout" in str(exc).lower():
                raise StopAsyncIteration from exc
            raise

    async def __aenter__(self) -> PulsarConsumer:
        if self._consumer is None:
            await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Outbox dispatcher
# ---------------------------------------------------------------------------


class PulsarOutboxDispatcher:
    """Publish pending outbox records to Pulsar and mark them dispatched.

    Parameters
    ----------
    producer:
        A configured :class:`PulsarProducer`.
    outbox_repo:
        The :class:`~mp_commons.kernel.messaging.outbox.OutboxRepository`.
    """

    def __init__(self, producer: PulsarProducer, outbox_repo: Any) -> None:
        self._producer = producer
        self._repo = outbox_repo

    async def dispatch_pending(self) -> int:
        """Publish pending records and return the dispatch count."""

        if self._producer._client is None:
            await self._producer.connect()

        records = await self._repo.get_pending()
        dispatched = 0
        for record in records:
            try:
                topic_producer = self._producer._get_producer(record.topic)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, topic_producer.send, record.payload)
                await self._repo.mark_dispatched(record.id)
                dispatched += 1
            except Exception:
                await self._repo.mark_failed(record.id, error="pulsar dispatch failed")
        return dispatched


__all__ = [
    "PulsarConsumer",
    "PulsarOutboxDispatcher",
    "PulsarProducer",
]
