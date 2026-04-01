from __future__ import annotations

import asyncio
import functools
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "ConsoleEventEmitter",
    "EventEmitter",
    "SchemaVersionError",
    "StructuredEvent",
    "instrument",
]

#: The schema version this library writes.  Consumers should reject events
#: whose ``schema_version`` exceeds this value.
CURRENT_SCHEMA_VERSION: int = 1

T = TypeVar("T")


class SchemaVersionError(ValueError):
    """Raised when an event carries a ``schema_version`` that is newer than
    :data:`CURRENT_SCHEMA_VERSION` and therefore cannot be safely processed."""


def _default_serializer(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


@dataclass
class StructuredEvent:
    name: str
    service: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: str | None = None
    duration_ms: float | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    #: Schema version for backward-compatible evolution.  Always 1 for events
    #: produced by this library.  Consumers must reject events where this value
    #: exceeds :data:`CURRENT_SCHEMA_VERSION`.
    schema_version: int = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "service": self.service,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "duration_ms": self.duration_ms,
            **self.fields,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=_default_serializer)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructuredEvent":
        """Deserialize a :class:`StructuredEvent` from a plain dictionary.

        Raises :class:`SchemaVersionError` if ``data["schema_version"]``
        exceeds :data:`CURRENT_SCHEMA_VERSION` — forward-compatibility guard.
        """
        version = int(data.get("schema_version", 1))
        if version > CURRENT_SCHEMA_VERSION:
            raise SchemaVersionError(
                f"Cannot deserialize StructuredEvent with schema_version={version}; "
                f"this library only supports up to version {CURRENT_SCHEMA_VERSION}. "
                "Upgrade mp-commons to process this event."
            )
        reserved = {"schema_version", "name", "service", "timestamp", "trace_id", "duration_ms"}
        ts_raw = data.get("timestamp")
        timestamp = (
            datetime.fromisoformat(ts_raw)
            if isinstance(ts_raw, str)
            else (ts_raw or datetime.now(timezone.utc))
        )
        return cls(
            name=data["name"],
            service=data["service"],
            timestamp=timestamp,
            trace_id=data.get("trace_id"),
            duration_ms=data.get("duration_ms"),
            fields={k: v for k, v in data.items() if k not in reserved},
            schema_version=version,
        )


class EventEmitter:
    """Batches StructuredEvents and ships them on flush."""

    def __init__(self) -> None:
        self._buffer: list[StructuredEvent] = []

    def emit(self, event: StructuredEvent) -> None:
        self._buffer.append(event)

    async def flush(self) -> int:
        count = len(self._buffer)
        self._buffer.clear()
        return count

    @property
    def buffered(self) -> list[StructuredEvent]:
        return list(self._buffer)


class ConsoleEventEmitter(EventEmitter):
    """Writes JSON lines to stdout for local development."""

    def emit(self, event: StructuredEvent) -> None:
        super().emit(event)
        print(event.to_json(), flush=True)  # noqa: T201


def instrument(
    name: str | None = None,
    service: str = "unknown",
    emitter: EventEmitter | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator — captures duration and emits a StructuredEvent on completion."""

    _emitter = emitter or EventEmitter()

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        event_name = name or fn.__qualname__

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            start = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
                return result
            finally:
                duration = (time.monotonic() - start) * 1000
                evt = StructuredEvent(
                    name=event_name,
                    service=service,
                    duration_ms=duration,
                )
                _emitter.emit(evt)

        wrapper._emitter = _emitter  # type: ignore[attr-defined]
        return wrapper

    return decorator
