"""AWS SQS task-bus adapter — implements :class:`TaskBus` (A-07).

Dispatches tasks as JSON messages to an SQS queue using ``aiobotocore``.
Supports:

* Standard and FIFO queues (``queue_url`` ending in ``.fifo``)
* Delivery delay via ``countdown`` seconds (max 900 s for SQS)
* FIFO queue attributes: ``MessageGroupId`` and optional ``MessageDeduplicationId``

Usage::

    from mp_commons.adapters.sqs import SQSTaskBus

    bus = SQSTaskBus(
        queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/my-tasks.fifo",
        region_name="us-east-1",
    )
    task_id = await bus.dispatch(
        "send_invoice",
        {"order_id": "ord-42"},
        message_group_id="invoices",
    )
"""

from __future__ import annotations

import json
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


def _require_aiobotocore() -> Any:
    try:
        import aiobotocore.session  # type: ignore[import-untyped]

        return aiobotocore.session
    except ImportError as exc:
        raise ImportError(
            "aiobotocore is required for SQSTaskBus. "
            "Install it with: pip install 'aiobotocore>=2.7'"
        ) from exc


class SQSTaskBus:
    """Async :class:`~mp_commons.adapters.celery.task_bus.TaskBus` backed by AWS SQS.

    Parameters
    ----------
    queue_url:
        The full SQS queue URL.  For FIFO queues the URL must end in ``.fifo``.
    region_name:
        AWS region (e.g. ``"us-east-1"``).
    aws_access_key_id:
        Optional explicit AWS access key (falls back to environment / IAM role).
    aws_secret_access_key:
        Optional explicit AWS secret key.
    aws_session_token:
        Optional session token for temporary credentials.
    endpoint_url:
        Override the SQS endpoint (useful for LocalStack testing).
    default_message_group_id:
        Default ``MessageGroupId`` for FIFO queues.  Required when the queue
        is FIFO and no per-message group is supplied.
    """

    def __init__(
        self,
        queue_url: str,
        region_name: str = "us-east-1",
        *,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        endpoint_url: str | None = None,
        default_message_group_id: str = "default",
    ) -> None:
        self._queue_url = queue_url
        self._region_name = region_name
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token
        self._endpoint_url = endpoint_url
        self._default_message_group_id = default_message_group_id
        self._is_fifo = queue_url.endswith(".fifo")

    async def dispatch(
        self,
        task_name: str,
        payload: dict[str, Any],
        *,
        queue: str = "default",
        countdown: int = 0,
        message_group_id: str | None = None,
        message_deduplication_id: str | None = None,
    ) -> str:
        """Enqueue *task_name* as a JSON SQS message.

        Parameters
        ----------
        task_name:
            Logical name of the task (stored as a message attribute and in
            the JSON body so consumers can route by task type).
        payload:
            JSON-serialisable dict of task arguments.
        queue:
            Logical queue name; currently ignored (all messages go to
            *queue_url* supplied at construction).  Kept for interface parity
            with :class:`~mp_commons.adapters.celery.task_bus.TaskBus`.
        countdown:
            Delay in seconds before the message becomes visible.  Capped at
            900 s (SQS maximum).
        message_group_id:
            FIFO queue message group ID.  Defaults to *default_message_group_id*.
        message_deduplication_id:
            FIFO queue deduplication ID.  Defaults to a fresh UUID4 (unique
            per dispatch; use content-based deduplication at the queue level
            for idempotent behaviour instead).

        Returns
        -------
        str
            The SQS ``MessageId`` string assigned by AWS.
        """
        aio_session = _require_aiobotocore()
        session = aio_session.AioSession()

        body = json.dumps({"task": task_name, "payload": payload})
        kwargs: dict[str, Any] = {
            "QueueUrl": self._queue_url,
            "MessageBody": body,
            "MessageAttributes": {
                "TaskName": {
                    "StringValue": task_name,
                    "DataType": "String",
                },
            },
        }
        if countdown:
            kwargs["DelaySeconds"] = min(countdown, 900)

        if self._is_fifo:
            kwargs["MessageGroupId"] = message_group_id or self._default_message_group_id
            kwargs["MessageDeduplicationId"] = message_deduplication_id or str(uuid.uuid4())

        client_kwargs: dict[str, Any] = {"region_name": self._region_name}
        if self._aws_access_key_id:
            client_kwargs["aws_access_key_id"] = self._aws_access_key_id
        if self._aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = self._aws_secret_access_key
        if self._aws_session_token:
            client_kwargs["aws_session_token"] = self._aws_session_token
        if self._endpoint_url:
            client_kwargs["endpoint_url"] = self._endpoint_url

        async with session.create_client("sqs", **client_kwargs) as client:
            response = await client.send_message(**kwargs)
            message_id: str = response["MessageId"]
            logger.info(
                "sqs.dispatched task=%s queue_url=%s message_id=%s",
                task_name,
                self._queue_url,
                message_id,
            )
            return message_id


__all__ = ["SQSTaskBus"]
