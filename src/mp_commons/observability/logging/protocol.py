"""Observability – Logger protocol and LogEvent."""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclasses.dataclass(frozen=True)
class LogEvent:
    """Structured log entry."""
    level: str
    message: str
    logger_name: str
    timestamp: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    tenant_id: str | None = None
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)


class Logger(Protocol):
    """Minimal logger protocol – works with structlog or stdlib."""

    def debug(self, event: str, **kw: Any) -> None: ...
    def info(self, event: str, **kw: Any) -> None: ...
    def warning(self, event: str, **kw: Any) -> None: ...
    def error(self, event: str, **kw: Any) -> None: ...
    def critical(self, event: str, **kw: Any) -> None: ...


__all__ = ["LogEvent", "Logger"]
