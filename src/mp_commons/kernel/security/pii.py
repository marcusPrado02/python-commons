"""Kernel security – PII redaction port and default sensitive fields."""
from __future__ import annotations

import re
from typing import Any, Protocol


class PIIRedactor(Protocol):
    """Port: redact personally identifiable information from log records."""

    def redact(self, data: dict[str, Any]) -> dict[str, Any]: ...


DEFAULT_SENSITIVE_FIELDS: frozenset[str] = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "credit_card", "card_number", "cvv", "ssn", "cpf", "cnpj",
})

# Patterns: (compiled regex, replacement label)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?:\+?\d[\s\-\.]?){9,14}\d")
_CPF_RE   = re.compile(r"\b\d{3}\.\d{3}\.\d{3}[\-/]\d{2}\b")
_CARD_RE  = re.compile(r"\b(?:\d[ \-]?){15,16}\b")

_TEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_EMAIL_RE, "[EMAIL]"),
    (_CPF_RE,   "[CPF]"),
    (_CARD_RE,  "[CARD]"),
    (_PHONE_RE, "[PHONE]"),
)


class RegexPIIRedactor:
    """Concrete PII redactor: masks sensitive dict keys and inline patterns.

    - Dict keys matching :data:`sensitive_fields` get replaced with ``'***'``.
    - String values are scanned with :data:`_TEXT_PATTERNS` regexes.
    - Nested dicts are redacted recursively.
    """

    def __init__(
        self,
        sensitive_fields: frozenset[str] = DEFAULT_SENSITIVE_FIELDS,
    ) -> None:
        self._sensitive_fields = sensitive_fields

    def redact(self, data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in self._sensitive_fields:
                result[key] = "***"
            elif isinstance(value, dict):
                result[key] = self.redact(value)
            elif isinstance(value, str):
                result[key] = self._redact_text(value)
            else:
                result[key] = value
        return result

    def _redact_text(self, text: str) -> str:
        for pattern, replacement in _TEXT_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


__all__ = ["DEFAULT_SENSITIVE_FIELDS", "PIIRedactor", "RegexPIIRedactor"]
