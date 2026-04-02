"""Kernel contracts – compatibility modes."""

from __future__ import annotations

from enum import StrEnum


class CompatibilityMode(StrEnum):
    """Schema registry compatibility rules."""

    BACKWARD = "BACKWARD"
    FORWARD = "FORWARD"
    FULL = "FULL"
    NONE = "NONE"


__all__ = ["CompatibilityMode"]
