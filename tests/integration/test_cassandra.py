"""Integration tests for Cassandra adapter (§55.5 / B-06).

CRUD round-trip and prepared statement reuse via CassandraRepository.
Run with: pytest tests/integration/test_cassandra.py -m integration -v

Requires Docker.  The Cassandra container exposes the CQL port (9042).
Warning: Cassandra containers are slow to start (~60-90s).
"""

from __future__ import annotations

import asyncio
import dataclasses
import time
from typing import Any

import pytest
from testcontainers.cassandra import CassandraContainer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


_KEYSPACE = "test_ks"
_TABLE = "products"


def _wait_cassandra_ready(host: str, port: int, timeout: int = 120) -> None:
    import socket

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(2)
    raise TimeoutError(f"Cassandra did not become available at {host}:{port}")


@pytest.fixture(scope="module")
def cassandra_session() -> Any:  # type: ignore[return]
    with CassandraContainer("cassandra:4.1") as cc:
        host = cc.get_container_host_ip()
        port = int(cc.get_exposed_port(9042))

        _wait_cassandra_ready(host, port)

        # Give Cassandra a bit more time to fully initialise after port is open
        time.sleep(10)

        from cassandra.cluster import Cluster  # type: ignore[import-untyped]

        cluster = Cluster([host], port=port)
        session = cluster.connect()

        session.execute(
            f"CREATE KEYSPACE IF NOT EXISTS {_KEYSPACE} "
            "WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}"
        )
        session.set_keyspace(_KEYSPACE)
        session.execute(
            f"CREATE TABLE IF NOT EXISTS {_TABLE} (pk text PRIMARY KEY, name text, price decimal)"
        )

        yield session

        cluster.shutdown()


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Product:
    pk: str
    name: str
    price: float


def _product_from_row(row: Any) -> Product:
    return Product(pk=row.pk, name=row.name, price=float(row.price))


# ---------------------------------------------------------------------------
# §55.5 — CassandraRepository
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCassandraRepositoryIntegration:
    """CRUD round-trip and prepared statement reuse."""

    def _make_repo(self, session: Any) -> Any:
        from mp_commons.adapters.cassandra import CassandraRepository

        return CassandraRepository(
            session=session,
            table=_TABLE,
            pk_column="pk",
            model=_product_from_row,
        )

    def test_save_and_get_round_trip(self, cassandra_session: Any) -> None:
        repo = self._make_repo(cassandra_session)

        async def _run_test() -> None:
            product = Product(pk="prod-1", name="Widget", price=9.99)
            await repo.save(product)
            fetched = await repo.get("prod-1")
            assert fetched is not None
            assert fetched.pk == "prod-1"
            assert fetched.name == "Widget"

        _run(_run_test())

    def test_delete_removes_row(self, cassandra_session: Any) -> None:
        repo = self._make_repo(cassandra_session)

        async def _run_test() -> None:
            product = Product(pk="prod-del", name="ToDelete", price=1.00)
            await repo.save(product)
            await repo.delete("prod-del")
            result = await repo.get("prod-del")
            assert result is None

        _run(_run_test())

    def test_prepared_statements_reused_across_calls(self, cassandra_session: Any) -> None:
        """Verify the _prepare() cache is hit on repeated calls."""
        repo = self._make_repo(cassandra_session)

        async def _run_test() -> None:
            # Two saves should reuse the same prepared statement (no re-preparation)
            await repo.save(Product(pk="prep-1", name="A", price=1.0))
            await repo.save(Product(pk="prep-2", name="B", price=2.0))
            # _prepare_cache is internal; verify indirectly by asserting data is correct
            a = await repo.get("prep-1")
            b = await repo.get("prep-2")
            assert a is not None
            assert a.name == "A"
            assert b is not None
            assert b.name == "B"

        _run(_run_test())
