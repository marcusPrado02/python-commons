"""Unit tests for the DynamoDB adapter (§54)."""
from __future__ import annotations

import asyncio
import dataclasses
import sys
import types
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mp_commons.adapters.dynamodb.repository import (
    DynamoDBIdempotencyStore,
    DynamoDBOutboxStore,
    DynamoDBRepository,
    DynamoDBTable,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_table_mock(**method_returns: Any) -> MagicMock:
    table = MagicMock()
    for method, retval in method_returns.items():
        setattr(table, method, AsyncMock(return_value=retval))
    return table


def _make_session(table_mock: MagicMock) -> MagicMock:
    """Return a mock aioboto3 session whose DynamoDB resource yields the table."""

    @asynccontextmanager
    async def _resource_cm(*args: Any, **kwargs: Any):
        db = MagicMock()
        db.Table = AsyncMock(return_value=table_mock)
        yield db

    session = MagicMock()
    session.resource = MagicMock(return_value=_resource_cm())
    return session


from typing import Any


# ---------------------------------------------------------------------------
# DynamoDBTable config
# ---------------------------------------------------------------------------


def test_table_config_defaults():
    tbl = DynamoDBTable("users")
    assert tbl.pk_field == "pk"
    assert tbl.sk_field is None


def test_table_config_custom():
    tbl = DynamoDBTable("orders", pk_field="order_id", sk_field="created_at")
    assert tbl.sk_field == "created_at"


# ---------------------------------------------------------------------------
# DynamoDBRepository
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _Item:
    pk: str
    name: str = ""


def _make_repo(table_mock: MagicMock) -> DynamoDBRepository[_Item]:
    config = DynamoDBTable("test-table")
    repo: DynamoDBRepository[_Item] = DynamoDBRepository.__new__(DynamoDBRepository)
    repo._config = config
    repo._model = _Item
    repo._region = "us-east-1"
    repo._endpoint_url = None

    @asynccontextmanager
    async def _res_ctx():
        db = MagicMock()
        db.Table = AsyncMock(return_value=table_mock)
        yield db

    repo._resource_context = _res_ctx
    return repo


def test_repo_get_returns_item():
    table = _make_table_mock(get_item={"Item": {"pk": "1", "name": "Alice"}})
    repo = _make_repo(table)

    result = asyncio.run(repo.get("1"))
    assert isinstance(result, _Item)
    assert result.name == "Alice"
    table.get_item.assert_called_once_with(Key={"pk": "1"})


def test_repo_get_returns_none_for_missing():
    table = _make_table_mock(get_item={"Item": None})
    table.get_item = AsyncMock(return_value={})  # no 'Item' key
    repo = _make_repo(table)

    result = asyncio.run(repo.get("missing"))
    assert result is None


def test_repo_put_calls_put_item():
    table = _make_table_mock(put_item=None)
    repo = _make_repo(table)
    item = _Item(pk="42", name="Bob")

    asyncio.run(repo.put(item))
    table.put_item.assert_called_once()
    call_kwargs = table.put_item.call_args[1]
    assert call_kwargs["Item"]["pk"] == "42"


def test_repo_delete_calls_delete_item():
    table = _make_table_mock(delete_item=None)
    repo = _make_repo(table)

    asyncio.run(repo.delete("1"))
    table.delete_item.assert_called_once_with(Key={"pk": "1"})


def test_repo_scan_returns_items():
    table = _make_table_mock(scan={"Items": [{"pk": "1", "name": "A"}, {"pk": "2", "name": "B"}]})
    repo = _make_repo(table)

    results = asyncio.run(repo.scan())
    assert len(results) == 2
    assert results[0].name == "A"


# ---------------------------------------------------------------------------
# DynamoDBIdempotencyStore
# ---------------------------------------------------------------------------


def _make_idem_store(table_mock: MagicMock) -> DynamoDBIdempotencyStore:
    store = DynamoDBIdempotencyStore.__new__(DynamoDBIdempotencyStore)
    store._table_name = "idem-table"
    store._region = "us-east-1"
    store._endpoint_url = None

    @asynccontextmanager
    async def _res_ctx():
        db = MagicMock()
        db.Table = AsyncMock(return_value=table_mock)
        yield db

    store._resource_context = _res_ctx
    return store


def test_idem_store_get_returns_record():
    table = _make_table_mock(get_item={"Item": {"key": "op:k1", "status": "COMPLETED", "response": b"ok"}})
    from mp_commons.kernel.messaging.idempotency import IdempotencyKey

    store = _make_idem_store(table)
    key = IdempotencyKey(client_key="k1", operation="op")

    result = asyncio.run(store.get(key))
    assert result is not None
    assert result.status == "COMPLETED"


def test_idem_store_get_returns_none():
    table = _make_table_mock(get_item={})
    from mp_commons.kernel.messaging.idempotency import IdempotencyKey

    store = _make_idem_store(table)
    key = IdempotencyKey(client_key="missing", operation="op")

    result = asyncio.run(store.get(key))
    assert result is None


def test_idem_store_complete_updates():
    table = _make_table_mock(update_item=None)
    from mp_commons.kernel.messaging.idempotency import IdempotencyKey

    store = _make_idem_store(table)
    key = IdempotencyKey(client_key="k", operation="op")

    asyncio.run(store.complete(key, b"result"))
    table.update_item.assert_called_once()


def test_idem_conditional_check_failed_raises_conflict():
    class _CondErr(Exception):
        pass

    _CondErr.__name__ = "ConditionalCheckFailedException"

    table = MagicMock()
    table.get_item = AsyncMock(return_value={})
    table.put_item = AsyncMock(side_effect=_CondErr("ConditionalCheckFailed"))
    table.update_item = AsyncMock()

    from mp_commons.kernel.messaging.idempotency import IdempotencyKey, IdempotencyRecord
    from mp_commons.kernel.errors.domain import ConflictError

    store = _make_idem_store(table)
    key = IdempotencyKey(client_key="dup", operation="op")
    record = IdempotencyRecord(key="op:dup", status="PROCESSING")

    with pytest.raises(ConflictError):
        asyncio.run(store.save(key, record))
