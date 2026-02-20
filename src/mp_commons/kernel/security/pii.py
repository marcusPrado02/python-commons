"""Kernel security – PII redaction port and default sensitive fields."""
from __future__ import annotations

from typing import Any, Protocol


class PIIRedactor(Protocol):
    """Port: redact personally identifiable information from log records."""

    def redact(self, data: dict[str, Any]) -> dict[str, Any]: ...


DEFAULT_SENSITIVE_FIELDS: frozenset[str] = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "credit_card", "card_number", "cvv", "ssn", "cpf", "cnpj",
})

__all__ = ["DEFAULT_SENSITIVE_FIELDS", "PIIRedactor"]
