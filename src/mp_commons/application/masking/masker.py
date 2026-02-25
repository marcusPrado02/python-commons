from __future__ import annotations

import fnmatch
import hashlib
import uuid
from typing import Any

from mp_commons.application.masking.rules import MaskingRule

__all__ = ["DataMasker"]


def _redact(value: Any, rule: MaskingRule) -> str:
    return "***"


def _hash(value: Any, rule: MaskingRule) -> str:
    raw = f"{rule.salt}{value}".encode()
    return hashlib.sha256(raw).hexdigest()[:8]


def _partial(value: Any, rule: MaskingRule) -> str:
    s = str(value)
    start = rule.partial_show_start
    end = rule.partial_show_end
    length = len(s)
    if length <= start + end:
        return "*" * length
    hidden = "*" * (length - start - end)
    return s[:start] + hidden + (s[-end:] if end else "")


def _tokenize(value: Any, rule: MaskingRule) -> str:
    raw = f"{rule.salt}{value}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    # Produce a deterministic UUID-shaped token
    return str(uuid.UUID(digest[:32]))


_STRATEGY_FN = {
    "redact": _redact,
    "hash": _hash,
    "partial": _partial,
    "tokenize": _tokenize,
}


class DataMasker:
    """Recursively masks dict values according to field-pattern rules."""

    def mask(self, data: dict[str, Any], rules: list[MaskingRule]) -> dict[str, Any]:
        return self._walk(data, rules)

    def _walk(self, node: Any, rules: list[MaskingRule]) -> Any:
        if isinstance(node, dict):
            return {k: self._apply_rules(k, v, rules) for k, v in node.items()}
        if isinstance(node, list):
            return [self._walk(item, rules) for item in node]
        return node

    def _apply_rules(self, key: str, value: Any, rules: list[MaskingRule]) -> Any:
        for rule in rules:
            if fnmatch.fnmatch(key, rule.field_pattern):
                fn = _STRATEGY_FN[rule.strategy]
                return fn(value, rule)
        # Recurse into nested structures
        return self._walk(value, rules)
