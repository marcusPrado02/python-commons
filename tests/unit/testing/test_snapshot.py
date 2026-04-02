"""Unit tests for §91 – Snapshot Testing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
import tempfile
from uuid import UUID

import pytest

from mp_commons.testing.snapshot import (
    SnapshotAsserter,
    SnapshotSerializer,
    SnapshotStore,
)


class _Color(Enum):
    RED = "red"
    BLUE = "blue"


@dataclass
class _Point:
    x: float
    y: float


class TestSnapshotSerializer:
    def test_basic_dict(self):
        s = SnapshotSerializer()
        result = s.serialize({"b": 2, "a": 1})
        assert '"a": 1' in result
        assert '"b": 2' in result

    def test_sorted_keys(self):
        s = SnapshotSerializer()
        result = s.serialize({"z": 3, "a": 1, "m": 2})
        keys = [k for k in ["a", "m", "z"] if k in result]
        assert keys == ["a", "m", "z"]

    def test_datetime_serialised(self):
        s = SnapshotSerializer()
        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = s.serialize({"ts": dt})
        assert "2026-01-15" in result

    def test_uuid_serialised(self):
        s = SnapshotSerializer()
        uid = UUID("12345678-1234-5678-1234-567812345678")
        result = s.serialize({"id": uid})
        assert "12345678-1234-5678-1234-567812345678" in result

    def test_decimal_serialised(self):
        s = SnapshotSerializer()
        result = s.serialize({"price": Decimal("9.99")})
        assert "9.99" in result

    def test_enum_serialised(self):
        s = SnapshotSerializer()
        result = s.serialize({"color": _Color.RED})
        assert "red" in result

    def test_dataclass_serialised(self):
        s = SnapshotSerializer()
        pt = _Point(1.0, 2.0)
        result = s.serialize(pt)
        assert '"x"' in result

    def test_deterministic_output(self):
        s = SnapshotSerializer()
        val = {"b": [3, 1, 2], "a": {"nested": True}}
        r1 = s.serialize(val)
        r2 = s.serialize(val)
        assert r1 == r2


class TestSnapshotStore:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(tmpdir)
            store.save("my_snap", '{"x": 1}')
            loaded = store.load("my_snap")
            assert loaded == '{"x": 1}'

    def test_load_returns_none_when_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(tmpdir)
            assert store.load("missing") is None

    def test_exists_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(tmpdir)
            store.save("snap", "content")
            assert store.exists("snap") is True

    def test_exists_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(tmpdir)
            assert store.exists("ghost") is False

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(tmpdir)
            store.save("snap", "content")
            store.delete("snap")
            assert not store.exists("snap")


class TestSnapshotAsserter:
    def test_first_run_creates_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(tmpdir)
            asserter = SnapshotAsserter(store=store)
            asserter.assert_matches_snapshot({"key": "val"}, "test1")
            assert store.exists("test1")

    def test_second_run_passes_on_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(tmpdir)
            asserter = SnapshotAsserter(store=store)
            asserter.assert_matches_snapshot({"key": "val"}, "test1")
            # second run should pass without error
            asserter.assert_matches_snapshot({"key": "val"}, "test1")

    def test_mismatch_raises_assertion_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(tmpdir)
            asserter = SnapshotAsserter(store=store)
            asserter.assert_matches_snapshot({"key": "old"}, "test1")
            with pytest.raises(AssertionError, match="Snapshot mismatch"):
                asserter.assert_matches_snapshot({"key": "new"}, "test1")

    def test_update_mode_overwrites(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(tmpdir)
            asserter_normal = SnapshotAsserter(store=store)
            asserter_update = SnapshotAsserter(store=store, update=True)
            # Create initial snapshot
            asserter_normal.assert_matches_snapshot({"key": "old"}, "upd")
            # Overwrite with new value
            asserter_update.assert_matches_snapshot({"key": "new"}, "upd")
            # Normal asserter should now match the new value
            asserter_normal.assert_matches_snapshot({"key": "new"}, "upd")
