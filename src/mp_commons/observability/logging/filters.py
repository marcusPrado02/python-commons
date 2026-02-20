"""Observability – SensitiveFieldsFilter."""
from __future__ import annotations

from typing import Any

from mp_commons.kernel.security import DEFAULT_SENSITIVE_FIELDS


class SensitiveFieldsFilter:
    """Replace values of sensitive keys with ``[REDACTED]``."""

    REDACTED = "[REDACTED]"

    def __init__(self, sensitive_fields: frozenset[str] | None = None) -> None:
        self._fields = sensitive_fields or DEFAULT_SENSITIVE_FIELDS

    def redact(self, data: dict[str, Any]) -> dict[str, Any]:
        return {k: (self.REDACTED if k.lower() in self._fields else v) for k, v in data.items()}

    def redact_deep(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact nested dicts."""
        result: dict[str, Any] = {}
        for k, v in data.items():
            if k.lower() in self._fields:
                result[k] = self.REDACTED
            elif isinstance(v, dict):
                result[k] = self.redact_deep(v)
            else:
                result[k] = v
        return result


__all__ = ["SensitiveFieldsFilter"]
