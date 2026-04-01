"""Google Cloud Pub/Sub adapter — PubSubProducer and PubSubSubscriber (A-02).

Uses ``google-cloud-pubsub`` with Application Default Credentials.  Supports
both **push** and **pull** subscription modes.

Usage (producer)::

    from mp_commons.adapters.gcp_pubsub import PubSubProducer

    async with PubSubProducer(project_id="my-project", topic_id="orders") as producer:
        await producer.send({"event": "OrderCreated", "order_id": "o-1"})

Usage (subscriber — pull mode)::

    from mp_commons.adapters.gcp_pubsub import PubSubSubscriber

    async with PubSubSubscriber(
        project_id="my-project",
        subscription_id="orders-processor",
    ) as sub:
        async for message in sub.pull():
            process(message)
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


def _require_pubsub() -> Any:
    try:
        from google.cloud import pubsub_v1  # type: ignore[import-untyped]
        return pubsub_v1
    except ImportError as exc:
        raise ImportError(
            "google-cloud-pubsub is required for PubSubProducer/Subscriber. "
            "Install it with: pip install 'google-cloud-pubsub>=2.18'"
        ) from exc


class PubSubProducer:
    """Async Pub/Sub message producer.

    Parameters
    ----------
    project_id:
        GCP project ID.
    topic_id:
        Pub/Sub topic ID (not the full resource path).
    credentials:
        Optional explicit credentials object (``google.oauth2.credentials.Credentials``).
        Defaults to Application Default Credentials.
    """

    def __init__(
        self,
        project_id: str,
        topic_id: str,
        *,
        credentials: Any = None,
    ) -> None:
        self._project_id = project_id
        self._topic_id = topic_id
        self._credentials = credentials
        self._publisher: Any = None
        self._topic_path: str = ""

    async def __aenter__(self) -> "PubSubProducer":
        pubsub_v1 = _require_pubsub()
        kwargs: dict[str, Any] = {}
        if self._credentials:
            kwargs["credentials"] = self._credentials
        self._publisher = pubsub_v1.PublisherClient(**kwargs)
        self._topic_path = self._publisher.topic_path(self._project_id, self._topic_id)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._publisher is not None:
            # PublisherClient is not a context manager in older SDK versions
            try:
                self._publisher.close()
            except Exception:
                pass
            self._publisher = None

    async def send(self, payload: dict[str, Any], **attributes: str) -> str:
        """Publish *payload* as a JSON message.

        Parameters
        ----------
        payload:
            JSON-serialisable dict.
        **attributes:
            Optional Pub/Sub message attributes.

        Returns
        -------
        str
            The published message ID.
        """
        import asyncio
        data = json.dumps(payload).encode("utf-8")
        future = self._publisher.publish(self._topic_path, data, **attributes)
        # publish() returns a Future; run in executor for async compatibility
        message_id: str = await asyncio.get_event_loop().run_in_executor(None, future.result)
        logger.debug("pubsub.sent topic=%s message_id=%s", self._topic_path, message_id)
        return message_id

    async def send_batch(self, payloads: list[dict[str, Any]]) -> list[str]:
        """Publish multiple payloads; returns message IDs in order."""
        ids: list[str] = []
        for payload in payloads:
            mid = await self.send(payload)
            ids.append(mid)
        return ids


class PubSubSubscriber:
    """Async Pub/Sub pull subscriber.

    Parameters
    ----------
    project_id:
        GCP project ID.
    subscription_id:
        Pub/Sub subscription ID (not the full resource path).
    credentials:
        Optional explicit credentials.
    max_messages:
        Maximum messages to pull per batch (default: 10).
    """

    def __init__(
        self,
        project_id: str,
        subscription_id: str,
        *,
        credentials: Any = None,
        max_messages: int = 10,
    ) -> None:
        self._project_id = project_id
        self._subscription_id = subscription_id
        self._credentials = credentials
        self._max_messages = max_messages
        self._subscriber: Any = None
        self._subscription_path: str = ""

    async def __aenter__(self) -> "PubSubSubscriber":
        pubsub_v1 = _require_pubsub()
        kwargs: dict[str, Any] = {}
        if self._credentials:
            kwargs["credentials"] = self._credentials
        self._subscriber = pubsub_v1.SubscriberClient(**kwargs)
        self._subscription_path = self._subscriber.subscription_path(
            self._project_id, self._subscription_id
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._subscriber is not None:
            try:
                self._subscriber.close()
            except Exception:
                pass
            self._subscriber = None

    async def pull(self) -> AsyncIterator[dict[str, Any]]:
        """Pull messages and yield decoded JSON payloads.

        Each message is acknowledged immediately after successful decoding.
        On decode error, the message is left unacknowledged (to be redelivered).

        Yields
        ------
        dict
            Decoded JSON payload.
        """
        import asyncio
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._subscriber.pull(
                request={
                    "subscription": self._subscription_path,
                    "max_messages": self._max_messages,
                }
            ),
        )
        ack_ids: list[str] = []
        for received_message in response.received_messages:
            try:
                data = received_message.message.data
                payload = json.loads(data)
                ack_ids.append(received_message.ack_id)
                yield payload
            except Exception:
                logger.exception(
                    "pubsub.decode_error subscription=%s", self._subscription_path
                )

        if ack_ids:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._subscriber.acknowledge(
                    request={
                        "subscription": self._subscription_path,
                        "ack_ids": ack_ids,
                    }
                ),
            )


__all__ = ["PubSubProducer", "PubSubSubscriber"]
