"""DynamoDB adapter — repository, outbox store, and idempotency store.

Requires ``aioboto3>=13.0``.  All classes raise :class:`ImportError` when the
library is absent.  Use mocking in unit tests.
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

T = TypeVar("T")


def _require_aioboto3() -> Any:
    try:
        import aioboto3  # type: ignore[import-untyped]

        return aioboto3
    except ImportError as exc:
        raise ImportError(
            "aioboto3 is required for DynamoDB adapters. "
            "Install it with: pip install 'aioboto3>=13.0'"
        ) from exc


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DynamoDBTable:
    """Configuration for a DynamoDB table."""

    table_name: str
    pk_field: str = "pk"
    sk_field: str | None = None


# ---------------------------------------------------------------------------
# Generic repository
# ---------------------------------------------------------------------------


class DynamoDBRepository(Generic[T]):
    """Async DynamoDB repository with CRUD and query support.

    Parameters
    ----------
    session:
        An ``aioboto3.Session`` instance.
    table_config:
        :class:`DynamoDBTable` describing the target table.
    model:
        Callable that accepts a ``dict`` and returns a *T* instance.
    region:
        AWS region for the DynamoDB resource.
    endpoint_url:
        Override endpoint (useful for LocalStack).
    """

    def __init__(
        self,
        session: Any,
        table_config: DynamoDBTable,
        model: Any,
        *,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ) -> None:
        self._session = session
        self._config = table_config
        self._model = model
        self._region = region
        self._endpoint_url = endpoint_url

    def _resource_context(self) -> Any:
        kwargs: dict[str, Any] = {"region_name": self._region}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        return self._session.resource("dynamodb", **kwargs)

    async def get(self, pk: str, sk: str | None = None) -> T | None:
        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._config.table_name)
            key: dict[str, Any] = {self._config.pk_field: pk}
            if sk is not None and self._config.sk_field:
                key[self._config.sk_field] = sk
            resp = await table.get_item(Key=key)
            item = resp.get("Item")
            if item is None:
                return None
            return self._model(**item)

    async def put(self, item: T) -> None:
        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._config.table_name)
            body = _to_dict(item)
            await table.put_item(Item=body)

    async def delete(self, pk: str, sk: str | None = None) -> None:
        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._config.table_name)
            key: dict[str, Any] = {self._config.pk_field: pk}
            if sk is not None and self._config.sk_field:
                key[self._config.sk_field] = sk
            await table.delete_item(Key=key)

    async def query(self, pk: str, sk_prefix: str | None = None) -> list[T]:
        from boto3.dynamodb.conditions import Key  # type: ignore[import-untyped]

        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._config.table_name)
            key_cond = Key(self._config.pk_field).eq(pk)
            if sk_prefix and self._config.sk_field:
                key_cond = key_cond & Key(self._config.sk_field).begins_with(sk_prefix)
            resp = await table.query(KeyConditionExpression=key_cond)
            return [self._model(**item) for item in resp.get("Items", [])]

    async def scan(self, filter_expr: Any = None) -> list[T]:
        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._config.table_name)
            kwargs: dict[str, Any] = {}
            if filter_expr is not None:
                kwargs["FilterExpression"] = filter_expr
            resp = await table.scan(**kwargs)
            return [self._model(**item) for item in resp.get("Items", [])]


# ---------------------------------------------------------------------------
# Outbox store
# ---------------------------------------------------------------------------


class DynamoDBOutboxStore:
    """DynamoDB-backed outbox record store.

    Stores :class:`~mp_commons.kernel.messaging.outbox.OutboxRecord` items and
    queries pending records via a ``status`` GSI.
    """

    _INDEX_NAME = "status-index"

    def __init__(
        self,
        session: Any,
        table_name: str,
        *,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ) -> None:
        self._session = session
        self._table_name = table_name
        self._region = region
        self._endpoint_url = endpoint_url

    def _resource_context(self) -> Any:
        kwargs: dict[str, Any] = {"region_name": self._region}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        return self._session.resource("dynamodb", **kwargs)

    async def save(self, record: Any) -> None:
        import dataclasses as _dc

        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            item = _dc.asdict(record)
            # Convert datetime to ISO string
            item["created_at"] = record.created_at.isoformat()
            if record.dispatched_at:
                item["dispatched_at"] = record.dispatched_at.isoformat()
            await table.put_item(Item=item)

    async def get_pending(self, limit: int = 100) -> list[Any]:
        from boto3.dynamodb.conditions import Key  # type: ignore[import-untyped]
        from mp_commons.kernel.messaging.outbox import OutboxRecord, OutboxStatus

        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            resp = await table.query(
                IndexName=self._INDEX_NAME,
                KeyConditionExpression=Key("status").eq(OutboxStatus.PENDING.value),
                Limit=limit,
            )
            return [OutboxRecord(**item) for item in resp.get("Items", [])]

    async def mark_dispatched(self, record_id: str) -> None:
        from mp_commons.kernel.messaging.outbox import OutboxStatus

        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.update_item(
                Key={"id": record_id},
                UpdateExpression="SET #s = :s, dispatched_at = :da",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": OutboxStatus.DISPATCHED.value,
                    ":da": datetime.now(UTC).isoformat(),
                },
            )

    async def mark_failed(self, record_id: str, error: str) -> None:
        from mp_commons.kernel.messaging.outbox import OutboxStatus

        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.update_item(
                Key={"id": record_id},
                UpdateExpression="SET #s = :s, last_error = :e",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": OutboxStatus.FAILED.value,
                    ":e": error,
                },
            )


# ---------------------------------------------------------------------------
# Idempotency store
# ---------------------------------------------------------------------------


class DynamoDBIdempotencyStore:
    """TTL-backed idempotency store using DynamoDB conditional writes.

    Uses a ``conditional PutItem`` with ``attribute_not_exists(key)`` to
    prevent duplicate acquisitions.
    """

    def __init__(
        self,
        session: Any,
        table_name: str,
        *,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ) -> None:
        self._session = session
        self._table_name = table_name
        self._region = region
        self._endpoint_url = endpoint_url

    def _resource_context(self) -> Any:
        kwargs: dict[str, Any] = {"region_name": self._region}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        return self._session.resource("dynamodb", **kwargs)

    async def get(self, key: Any) -> Any | None:
        from mp_commons.kernel.messaging.idempotency import IdempotencyKey, IdempotencyRecord

        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            resp = await table.get_item(Key={"key": str(key)})
            item = resp.get("Item")
            if item is None:
                return None
            return IdempotencyRecord(
                key=item["key"],
                response=item.get("response"),
                status=item.get("status", "PROCESSING"),
            )

    async def save(self, key: Any, record: Any) -> None:
        from mp_commons.kernel.messaging.idempotency import IdempotencyKey

        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            item: dict[str, Any] = {
                "key": str(key),
                "status": record.status,
            }
            if record.response is not None:
                item["response"] = record.response
            if record.expires_at is not None:
                import calendar

                item["expires_at"] = calendar.timegm(record.expires_at.timetuple())
            try:
                await table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(#k)",
                    ExpressionAttributeNames={"#k": "key"},
                )
            except Exception as exc:
                if "ConditionalCheckFailed" in type(exc).__name__ or "ConditionalCheckFailed" in str(exc):
                    from mp_commons.kernel.errors.domain import ConflictError

                    raise ConflictError(f"Idempotency key {key} already exists") from exc
                raise

    async def complete(self, key: Any, response: bytes) -> None:
        async with self._resource_context() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.update_item(
                Key={"key": str(key)},
                UpdateExpression="SET #s = :s, response = :r",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "COMPLETED", ":r": response},
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)  # type: ignore[arg-type]
    return dict(vars(obj))


__all__ = [
    "DynamoDBIdempotencyStore",
    "DynamoDBOutboxStore",
    "DynamoDBRepository",
    "DynamoDBTable",
]
