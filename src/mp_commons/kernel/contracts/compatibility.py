"""Kernel contracts – compatibility modes."""
from __future__ import annotations
from enum import Enum


class CompatibilityMode(str, Enum):
    """Schema registry compatibility rules."""
    BACKWARD = "BACKWARD"
    FORWARD = "FORWARD"
    FULL = "FULL"
    NONE = "NONE"


__all__ = ["CompatibilityMode"]
