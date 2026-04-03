"""Unit tests for the Cassandra adapter (§55)."""

from __future__ import annotations

import asyncio
import dataclasses
from unittest.mock import MagicMock, patch

import pytest

from mp_commons.adapters.cassandra.repository import (
    CassandraOutboxStore,
    CassandraRepository,
    CassandraSessionFactory,
)

# ---------------------------------------------------------------------------
# CassandraSessionFactory
# ---------------------------------------------------------------------------


def test_session_factory_delegates_kwargs():
    with patch(
        "mp_commons.adapters.cassandra.repository._require_cassandra", return_value=MagicMock()
    ):
        factory = CassandraSessionFactory(["localhost"], "my_keyspace", port=9042)
        assert factory._contact_points == ["localhost"]
        assert factory._keyspace == "my_keyspace"
        assert factory._kwargs == {"port": 9042}


def test_session_property_raises_before_connect():
    with patch(
        "mp_commons.adapters.cassandra.repository._require_cassandra", return_value=MagicMock()
    ):
        factory = CassandraSessionFactory(["localhost"], "ks")
        with pytest.raises(RuntimeError, match="connect()"):
            _ = factory.session


# ---------------------------------------------------------------------------
# CassandraRepository (mocked session)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _Row:
    id: str
    value: str = ""


def _named_tuple_row(id_: str, value: str = "") -> MagicMock:
    """Return a namedtuple-like mock row."""
    row = MagicMock()
    row._fields = ("id", "value")
    row.__iter__ = lambda self: iter((id_, value))
    row[0] = id_

    # Allow tuple unpacking via zip
    def to_iter(self):
        return iter((id_, value))

    return (id_, value)  # Use plain tuple for zip compatibility


def _make_row_named(id_: str, value: str = ""):
    """Create a simple namedtuple row compatible with zip(row._fields, row)."""
    from collections import namedtuple

    _R = namedtuple("_R", ["id", "value"])
    return _R(id=id_, value=value)


def _make_repo(session: MagicMock) -> CassandraRepository[_Row]:
    repo: CassandraRepository[_Row] = CassandraRepository.__new__(CassandraRepository)
    repo._session = session
    repo._table = "items"
    repo._model = lambda row: _Row(id=row.id, value=row.value)
    repo._pk_field = "id"
    repo._prepared = {}
    return repo


def test_repo_get_returns_item():
    row = _make_row_named("42", "hello")
    session = MagicMock()
    session.prepare = MagicMock(return_value="stmt")
    session.execute = MagicMock(return_value=[row])
    repo = _make_repo(session)

    result = asyncio.run(repo.get("42"))
    assert isinstance(result, _Row)
    assert result.id == "42"
    assert result.value == "hello"


def test_repo_get_returns_none_for_empty():
    session = MagicMock()
    session.prepare = MagicMock(return_value="stmt")
    session.execute = MagicMock(return_value=[])
    repo = _make_repo(session)

    result = asyncio.run(repo.get("missing"))
    assert result is None


def test_repo_save_calls_execute():
    session = MagicMock()
    session.prepare = MagicMock(return_value="stmt")
    session.execute = MagicMock(return_value=None)
    repo = _make_repo(session)
    item = _Row(id="1", value="test")

    asyncio.run(repo.save(item))
    session.execute.assert_called_once()


def test_repo_delete_calls_execute():
    session = MagicMock()
    session.prepare = MagicMock(return_value="stmt")
    session.execute = MagicMock(return_value=None)
    repo = _make_repo(session)

    asyncio.run(repo.delete("1"))
    session.execute.assert_called_once()


def test_repo_prepared_statements_reused():
    session = MagicMock()
    session.prepare = MagicMock(return_value="stmt")
    session.execute = MagicMock(return_value=[])
    repo = _make_repo(session)

    asyncio.run(repo.get("a"))
    asyncio.run(repo.get("b"))
    # prepare should only be called once per CQL string
    assert session.prepare.call_count == 1


def test_repo_find_by():
    row = _make_row_named("7", "blue")
    session = MagicMock()
    session.prepare = MagicMock(return_value="stmt")
    session.execute = MagicMock(return_value=[row])
    repo = _make_repo(session)

    results = asyncio.run(repo.find_by("value", "blue"))
    assert len(results) == 1
    assert results[0].value == "blue"


# ---------------------------------------------------------------------------
# CassandraOutboxStore (mocked session)
# ---------------------------------------------------------------------------


def test_outbox_bucket_hour():
    from datetime import datetime

    dt = datetime(2024, 3, 15, 14, 33, 0)
    assert CassandraOutboxStore._bucket_hour(dt) == "2024-03-15T14:00:00"
