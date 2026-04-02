"""Cassandra adapter — session factory, generic repository, and outbox store.

Requires ``cassandra-driver>=3.29``.  All classes raise :class:`ImportError`
when the library is absent.
"""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

T = TypeVar("T")


def _require_cassandra() -> Any:
    try:
        import cassandra  # type: ignore[import-untyped]

        return cassandra
    except ImportError as exc:
        raise ImportError(
            "cassandra-driver is required for Cassandra adapters. "
            "Install it with: pip install 'cassandra-driver>=3.29'"
        ) from exc


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------


class CassandraSessionFactory:
    """Create and manage Cassandra driver sessions.

    Parameters
    ----------
    contact_points:
        List of Cassandra node hostnames or IP addresses.
    keyspace:
        Default keyspace to use.
    **kwargs:
        Extra kwargs forwarded to :class:`cassandra.cluster.Cluster`.
    """

    def __init__(
        self,
        contact_points: list[str],
        keyspace: str,
        **kwargs: Any,
    ) -> None:
        _require_cassandra()
        self._contact_points = contact_points
        self._keyspace = keyspace
        self._kwargs = kwargs
        self._session: Any = None
        self._cluster: Any = None

    def connect(self) -> Any:
        """Connect and return a :class:`cassandra.cluster.Session`."""
        from cassandra.cluster import Cluster  # type: ignore[import-untyped]

        self._cluster = Cluster(self._contact_points, **self._kwargs)
        self._session = self._cluster.connect(self._keyspace)
        return self._session

    def close(self) -> None:
        """Gracefully close the cluster connection."""
        if self._cluster is not None:
            self._cluster.shutdown()

    @property
    def session(self) -> Any:
        if self._session is None:
            raise RuntimeError("Call connect() before using the session.")
        return self._session


# ---------------------------------------------------------------------------
# Generic repository (uses prepared statements)
# ---------------------------------------------------------------------------


class CassandraRepository(Generic[T]):
    """Async Cassandra repository using prepared statements.

    Parameters
    ----------
    session:
        A connected :class:`cassandra.cluster.Session`.
    table:
        The Cassandra table name (qualified with keyspace if needed).
    model:
        Callable accepting ``**kwargs`` to construct a *T* instance.
    pk_field:
        Primary key column name (default ``"id"``).  Alias: ``pk_column``.
    """

    def __init__(
        self,
        session: Any,
        table: str,
        model: Any,
        pk_field: str = "id",
        pk_column: str | None = None,
    ) -> None:
        self._session = session
        self._table = table
        self._model = model
        self._pk_field = pk_column if pk_column is not None else pk_field
        self._prepared: dict[str, Any] = {}

    def _prepare(self, cql: str) -> Any:
        if cql not in self._prepared:
            self._prepared[cql] = self._session.prepare(cql)
        return self._prepared[cql]

    async def _exec(self, cql: str, params: tuple | None = None) -> Any:
        stmt = self._prepare(cql)
        loop = asyncio.get_event_loop()
        if params:
            return await loop.run_in_executor(None, self._session.execute, stmt, params)
        return await loop.run_in_executor(None, self._session.execute, stmt)

    async def get(self, pk: Any) -> T | None:
        cql = f"SELECT * FROM {self._table} WHERE {self._pk_field} = ?"
        rows = await self._exec(cql, (pk,))
        if rows is not None:
            row_list = list(rows)
            if row_list:
                return self._model(**dict(zip(row_list[0]._fields, row_list[0], strict=False)))
        return None

    async def save(self, entity: T) -> None:
        body = _to_dict(entity)
        columns = ", ".join(body.keys())
        placeholders = ", ".join("?" * len(body))
        cql = f"INSERT INTO {self._table} ({columns}) VALUES ({placeholders})"
        await self._exec(cql, tuple(body.values()))

    async def delete(self, pk: Any) -> None:
        cql = f"DELETE FROM {self._table} WHERE {self._pk_field} = ?"
        await self._exec(cql, (pk,))

    async def find_by(self, column: str, value: Any) -> list[T]:
        cql = f"SELECT * FROM {self._table} WHERE {column} = ? ALLOW FILTERING"
        rows = await self._exec(cql, (value,))
        results: list[T] = []
        if rows:
            for row in rows:
                results.append(self._model(**dict(zip(row._fields, row, strict=False))))
        return results


# ---------------------------------------------------------------------------
# Outbox store
# ---------------------------------------------------------------------------


class CassandraOutboxStore:
    """Time-series outbox store partitioned by ``(topic, bucket_hour)``.

    ``get_pending`` queries the current and previous bucket to avoid missed
    records near bucket boundaries.
    """

    def __init__(self, session: Any, table: str = "outbox") -> None:
        self._session = session
        self._table = table

    @staticmethod
    def _bucket_hour(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:00:00")

    async def save(self, record: Any) -> None:
        loop = asyncio.get_event_loop()
        body = dataclasses.asdict(record)
        body["bucket_hour"] = self._bucket_hour(record.created_at)
        columns = ", ".join(body.keys())
        placeholders = ", ".join("?" * len(body))
        cql = f"INSERT INTO {self._table} ({columns}) VALUES ({placeholders})"
        stmt = self._session.prepare(cql)
        await loop.run_in_executor(None, self._session.execute, stmt, tuple(body.values()))

    async def get_pending(self, topic: str, limit: int = 100) -> list[Any]:
        from mp_commons.kernel.messaging.outbox import OutboxStatus

        loop = asyncio.get_event_loop()
        now = datetime.now(UTC)
        buckets = [self._bucket_hour(now)]
        # Also check previous hour
        from datetime import timedelta

        prev = now - timedelta(hours=1)
        buckets.append(self._bucket_hour(prev))

        cql = (
            f"SELECT * FROM {self._table} WHERE topic = ? AND bucket_hour = ? "
            f"AND status = ? LIMIT {limit} ALLOW FILTERING"
        )
        stmt = self._session.prepare(cql)
        results: list[Any] = []
        for bucket in buckets:
            rows = await loop.run_in_executor(
                None,
                self._session.execute,
                stmt,
                (topic, bucket, OutboxStatus.PENDING.value),
            )
            if rows:
                for row in rows:
                    results.append(row)
        return results

    async def mark_dispatched(self, record_id: str) -> None:
        from mp_commons.kernel.messaging.outbox import OutboxStatus

        loop = asyncio.get_event_loop()
        cql = f"UPDATE {self._table} SET status = ? WHERE id = ?"
        stmt = self._session.prepare(cql)
        await loop.run_in_executor(
            None,
            self._session.execute,
            stmt,
            (OutboxStatus.DISPATCHED.value, record_id),
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
    "CassandraOutboxStore",
    "CassandraRepository",
    "CassandraSessionFactory",
]
