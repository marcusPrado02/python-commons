"""Azure Service Bus adapter — AzureServiceBusProducer and Consumer (A-01).

Implements the same ``MessageBus`` protocol as the Kafka/NATS adapters using
``azure-servicebus`` with managed-identity authentication via
``azure-identity``.

Usage (producer)::

    from mp_commons.adapters.azure_servicebus import AzureServiceBusProducer

    producer = AzureServiceBusProducer(
        fully_qualified_namespace="myns.servicebus.windows.net",
        queue_or_topic="orders",
    )
    async with producer:
        await producer.send({"event_type": "OrderCreated", "order_id": "o-1"})

Usage (consumer)::

    from mp_commons.adapters.azure_servicebus import AzureServiceBusConsumer

    consumer = AzureServiceBusConsumer(
        fully_qualified_namespace="myns.servicebus.windows.net",
        queue_or_topic="orders",
        subscription="order-processor",  # omit for queues
    )
    async with consumer:
        async for message in consumer.receive():
            process(message)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _require_servicebus() -> Any:
    try:
        from azure.servicebus.aio import ServiceBusClient  # type: ignore[import-untyped]

        return ServiceBusClient
    except ImportError as exc:
        raise ImportError(
            "azure-servicebus is required for AzureServiceBusProducer/Consumer. "
            "Install it with: pip install 'azure-servicebus>=7.11'"
        ) from exc


def _require_identity() -> Any:
    try:
        from azure.identity.aio import DefaultAzureCredential  # type: ignore[import-untyped]

        return DefaultAzureCredential
    except ImportError as exc:
        raise ImportError(
            "azure-identity is required for managed-identity auth. "
            "Install it with: pip install 'azure-identity>=1.15'"
        ) from exc


class AzureServiceBusProducer:
    """Async producer for Azure Service Bus queues and topics.

    Implements ``send`` / ``send_batch`` compatible with the ``MessageBus``
    protocol used by Kafka and NATS adapters.

    Parameters
    ----------
    fully_qualified_namespace:
        E.g. ``myns.servicebus.windows.net``.
    queue_or_topic:
        Target queue or topic name.
    connection_string:
        Optional connection string.  When supplied, managed identity is not
        used.  Prefer managed identity in production.
    max_wait_time:
        Seconds to wait for the broker acknowledgement (default: 30).
    """

    def __init__(
        self,
        fully_qualified_namespace: str,
        queue_or_topic: str,
        *,
        connection_string: str | None = None,
        max_wait_time: float = 30.0,
    ) -> None:
        self._namespace = fully_qualified_namespace
        self._entity = queue_or_topic
        self._connection_string = connection_string
        self._max_wait_time = max_wait_time
        self._client: Any = None

    async def __aenter__(self) -> AzureServiceBusProducer:
        ServiceBusClient = _require_servicebus()
        if self._connection_string:
            self._client = ServiceBusClient.from_connection_string(self._connection_string)
        else:
            credential = _require_identity()()
            self._client = ServiceBusClient(self._namespace, credential)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client is not None:
            await self._client.__aexit__(*_)
            self._client = None

    async def send(self, payload: dict[str, Any]) -> None:
        """Send a single JSON-serialised message."""
        _require_servicebus()
        from azure.servicebus import ServiceBusMessage  # type: ignore[import-untyped]

        body = json.dumps(payload)
        async with self._client.get_queue_sender(self._entity) as sender:
            msg = ServiceBusMessage(body)
            await sender.send_messages(msg)
            logger.debug("azure_servicebus.sent entity=%s", self._entity)

    async def send_batch(self, payloads: list[dict[str, Any]]) -> None:
        """Send a batch of messages atomically."""
        from azure.servicebus import ServiceBusMessage  # type: ignore[import-untyped]

        async with self._client.get_queue_sender(self._entity) as sender:
            batch = await sender.create_message_batch()
            for payload in payloads:
                batch.add_message(ServiceBusMessage(json.dumps(payload)))
            await sender.send_messages(batch)
            logger.debug(
                "azure_servicebus.sent_batch count=%d entity=%s", len(payloads), self._entity
            )


class AzureServiceBusConsumer:
    """Async consumer for Azure Service Bus queues and topic subscriptions.

    Parameters
    ----------
    fully_qualified_namespace:
        E.g. ``myns.servicebus.windows.net``.
    queue_or_topic:
        Source queue or topic name.
    subscription:
        Subscription name (required for topics; omit for queues).
    connection_string:
        Optional connection string.
    max_message_count:
        Maximum messages per ``receive()`` call (default: 10).
    max_wait_time:
        Seconds to wait for messages on each receive call (default: 5).
    """

    def __init__(
        self,
        fully_qualified_namespace: str,
        queue_or_topic: str,
        *,
        subscription: str | None = None,
        connection_string: str | None = None,
        max_message_count: int = 10,
        max_wait_time: float = 5.0,
    ) -> None:
        self._namespace = fully_qualified_namespace
        self._entity = queue_or_topic
        self._subscription = subscription
        self._connection_string = connection_string
        self._max_message_count = max_message_count
        self._max_wait_time = max_wait_time
        self._client: Any = None

    async def __aenter__(self) -> AzureServiceBusConsumer:
        ServiceBusClient = _require_servicebus()
        if self._connection_string:
            self._client = ServiceBusClient.from_connection_string(self._connection_string)
        else:
            credential = _require_identity()()
            self._client = ServiceBusClient(self._namespace, credential)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client is not None:
            await self._client.__aexit__(*_)
            self._client = None

    def _receiver(self) -> Any:
        if self._subscription:
            return self._client.get_subscription_receiver(
                self._entity,
                self._subscription,
                max_wait_time=self._max_wait_time,
            )
        return self._client.get_queue_receiver(
            self._entity,
            max_wait_time=self._max_wait_time,
        )

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        """Yield decoded JSON payloads; completes when the batch window closes.

        Callers are responsible for calling ``complete()`` on the underlying
        ServiceBusReceivedMessage — this interface decodes the payload only.
        """
        async with self._receiver() as receiver:
            async for msg in receiver:
                try:
                    body = b"".join(msg.body) if hasattr(msg.body, "__iter__") else msg.body
                    payload = json.loads(body)
                    yield payload
                    await receiver.complete_message(msg)
                except Exception:
                    logger.exception("azure_servicebus.receive_error entity=%s", self._entity)
                    await receiver.abandon_message(msg)


__all__ = ["AzureServiceBusConsumer", "AzureServiceBusProducer"]
