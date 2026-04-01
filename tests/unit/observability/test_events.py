"""Unit tests for §82 / O-05 – Observability Structured Events."""
import asyncio
import json

import pytest

from mp_commons.observability.events import (
    CURRENT_SCHEMA_VERSION,
    ConsoleEventEmitter,
    EventEmitter,
    SchemaVersionError,
    StructuredEvent,
    instrument,
)


class TestStructuredEvent:
    def test_to_dict_has_required_fields(self):
        evt = StructuredEvent(name="order.created", service="orders")
        d = evt.to_dict()
        assert d["name"] == "order.created"
        assert d["service"] == "orders"
        assert "timestamp" in d

    def test_to_json_parses(self):
        evt = StructuredEvent(name="test", service="svc", fields={"user_id": 1})
        parsed = json.loads(evt.to_json())
        assert parsed["name"] == "test"
        assert parsed["user_id"] == 1

    def test_extra_fields_included(self):
        evt = StructuredEvent(name="x", service="y", fields={"key": "val"})
        d = evt.to_dict()
        assert d["key"] == "val"

    def test_duration_ms_in_dict(self):
        evt = StructuredEvent(name="x", service="y", duration_ms=42.5)
        assert evt.to_dict()["duration_ms"] == 42.5


class TestEventEmitter:
    def test_emit_buffers_event(self):
        emitter = EventEmitter()
        emitter.emit(StructuredEvent("e1", "svc"))
        assert len(emitter.buffered) == 1

    def test_flush_clears_buffer_and_returns_count(self):
        emitter = EventEmitter()
        emitter.emit(StructuredEvent("e1", "svc"))
        emitter.emit(StructuredEvent("e2", "svc"))
        count = asyncio.run(emitter.flush())
        assert count == 2
        assert emitter.buffered == []

    def test_console_emitter_emits(self, capsys):
        emitter = ConsoleEventEmitter()
        emitter.emit(StructuredEvent("evx", "svc"))
        captured = capsys.readouterr()
        assert "evx" in captured.out


class TestInstrumentDecorator:
    def test_decorator_runs_function(self):
        emitter = EventEmitter()

        @instrument(name="my.op", service="test", emitter=emitter)
        async def operation(x: int) -> int:
            return x * 2

        result = asyncio.run(operation(5))
        assert result == 10

    def test_decorator_emits_event(self):
        emitter = EventEmitter()

        @instrument(name="compute", service="svc", emitter=emitter)
        async def compute():
            return 42

        asyncio.run(compute())
        assert len(emitter.buffered) == 1
        evt = emitter.buffered[0]
        assert evt.name == "compute"
        assert evt.duration_ms is not None and evt.duration_ms >= 0

    def test_decorator_propagates_exception(self):
        emitter = EventEmitter()

        @instrument(emitter=emitter)
        async def bad():
            raise ValueError("nope")

        with pytest.raises(ValueError):
            asyncio.run(bad())

    def test_default_name_is_qualname(self):
        emitter = EventEmitter()

        @instrument(emitter=emitter)
        async def my_func():
            return 1

        asyncio.run(my_func())
        assert "my_func" in emitter.buffered[0].name


class TestStructuredEventSchemaVersion:
    """O-05 — schema_version field and backward-compatible evolution."""

    def test_default_schema_version_is_current(self):
        evt = StructuredEvent(name="x", service="y")
        assert evt.schema_version == CURRENT_SCHEMA_VERSION

    def test_schema_version_in_to_dict(self):
        evt = StructuredEvent(name="x", service="y")
        assert evt.to_dict()["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_schema_version_in_json(self):
        evt = StructuredEvent(name="x", service="y")
        parsed = json.loads(evt.to_json())
        assert parsed["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_from_dict_round_trip(self):
        evt = StructuredEvent(
            name="order.created",
            service="orders",
            trace_id="abc",
            duration_ms=12.5,
            fields={"user_id": 42},
        )
        restored = StructuredEvent.from_dict(evt.to_dict())
        assert restored.name == evt.name
        assert restored.service == evt.service
        assert restored.trace_id == evt.trace_id
        assert restored.duration_ms == evt.duration_ms
        assert restored.fields.get("user_id") == 42
        assert restored.schema_version == CURRENT_SCHEMA_VERSION

    def test_from_dict_missing_version_defaults_to_1(self):
        data = {"name": "e", "service": "s", "timestamp": "2024-01-01T00:00:00+00:00"}
        evt = StructuredEvent.from_dict(data)
        assert evt.schema_version == 1

    def test_from_dict_rejects_future_version(self):
        data = {
            "schema_version": CURRENT_SCHEMA_VERSION + 1,
            "name": "e",
            "service": "s",
            "timestamp": "2024-01-01T00:00:00+00:00",
        }
        with pytest.raises(SchemaVersionError):
            StructuredEvent.from_dict(data)

    def test_schema_version_error_message_mentions_version(self):
        future = CURRENT_SCHEMA_VERSION + 5
        data = {"schema_version": future, "name": "e", "service": "s",
                "timestamp": "2024-01-01T00:00:00+00:00"}
        with pytest.raises(SchemaVersionError, match=str(future)):
            StructuredEvent.from_dict(data)

    def test_explicit_schema_version_preserved(self):
        evt = StructuredEvent(name="x", service="y", schema_version=1)
        assert evt.schema_version == 1
