"""Invariant helpers for asserting domain rules."""

from __future__ import annotations

from typing import TypeVar

from mp_commons.kernel.errors.domain import InvariantViolationError

T = TypeVar("T")


class Invariant:
    """Namespace for invariant assertions."""

    @staticmethod
    def require(condition: bool, message: str) -> None:
        """Raise ``InvariantViolationError`` when *condition* is False."""
        if not condition:
            raise InvariantViolationError(message)

    @staticmethod
    def not_none(value: T | None, name: str = "value") -> T:
        """Assert *value* is not None, returning it typed."""
        if value is None:
            raise InvariantViolationError(f"{name} must not be None")
        return value


def ensure(condition: bool, message: str) -> None:
    """Shorthand for ``Invariant.require``."""
    Invariant.require(condition, message)


__all__ = ["Invariant", "ensure"]
