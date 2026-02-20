"""Observability – CorrelationIdProvider protocol."""
from __future__ import annotations
from typing import Protocol


class CorrelationIdProvider(Protocol):
    """Port: extract a correlation ID from a raw transport header."""

    def extract(self, headers: dict[str, str]) -> str | None: ...

    def inject(self, headers: dict[str, str], correlation_id: str) -> dict[str, str]: ...


__all__ = ["CorrelationIdProvider"]
