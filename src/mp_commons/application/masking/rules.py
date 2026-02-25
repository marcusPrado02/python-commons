from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

__all__ = ["MaskingRule"]

MaskingStrategy = Literal["redact", "hash", "partial", "tokenize"]


@dataclass(frozen=True)
class MaskingRule:
    """Describes how to mask a field matching *field_pattern*."""

    field_pattern: str
    strategy: MaskingStrategy = "redact"
    salt: str = ""
    # For partial strategy: characters to show at start/end
    partial_show_start: int = 2
    partial_show_end: int = 2
