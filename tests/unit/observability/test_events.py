"""Unit tests for §82 – Observability Structured Events."""
import asyncio
import json

import pytest

from mp_commons.observability.events import (
    ConsoleEventEmitter,
    EventEmitter,
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
