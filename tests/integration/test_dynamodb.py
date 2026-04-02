"""Integration tests for DynamoDB adapter using LocalStack (§54.6 / B-05).

Run with: pytest tests/integration/test_dynamodb.py -m integration -v

Requires Docker.  LocalStack exposes the DynamoDB API on port 4566.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

import pytest
from testcontainers.localstack import LocalStackContainer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


_TABLE = "orders"
_REGION = "us-east-1"


@pytest.fixture(scope="module")
def dynamo_endpoint() -> str:  # type: ignore[return]
    with LocalStackContainer().with_services("dynamodb") as ls:
        endpoint = ls.get_url()

        # Create the table via boto3 (synchronous setup)
        import boto3

        client = boto3.client(
            "dynamodb",
            endpoint_url=endpoint,
            region_name=_REGION,
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        client.create_table(
            TableName=_TABLE,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield endpoint


# ---------------------------------------------------------------------------
# Domain model used in tests
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Order:
    pk: str
    customer_id: str
    status: str


# ---------------------------------------------------------------------------
# §54.6 — DynamoDBRepository
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDynamoDBRepositoryIntegration:
    """CRUD round-trip against LocalStack DynamoDB."""

    def _make_repo(self, endpoint: str) -> Any:
        import aioboto3  # type: ignore[import-untyped]

        from mp_commons.adapters.dynamodb import DynamoDBRepository, DynamoDBTable

        session = aioboto3.Session(
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        return DynamoDBRepository(
            session=session,
            table_config=DynamoDBTable(table_name=_TABLE, pk_field="pk"),
            model=Order,
            region=_REGION,
            endpoint_url=endpoint,
        )

    def test_put_and_get_round_trip(self, dynamo_endpoint: str) -> None:
        repo = self._make_repo(dynamo_endpoint)

        async def _run_test() -> None:
            order = Order(pk="ord-1", customer_id="cust-A", status="pending")
            await repo.put(order)
            fetched = await repo.get("ord-1")
            assert fetched is not None
            assert fetched.pk == "ord-1"
            assert fetched.customer_id == "cust-A"
            assert fetched.status == "pending"

        _run(_run_test())

    def test_delete_removes_item(self, dynamo_endpoint: str) -> None:
        repo = self._make_repo(dynamo_endpoint)

        async def _run_test() -> None:
            order = Order(pk="ord-del", customer_id="cust-B", status="shipped")
            await repo.put(order)
            await repo.delete("ord-del")
            fetched = await repo.get("ord-del")
            assert fetched is None

        _run(_run_test())

    def test_get_nonexistent_returns_none(self, dynamo_endpoint: str) -> None:
        repo = self._make_repo(dynamo_endpoint)

        async def _run_test() -> None:
            result = await repo.get("does-not-exist")
            assert result is None

        _run(_run_test())
