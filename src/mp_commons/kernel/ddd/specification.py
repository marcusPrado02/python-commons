"""Specification pattern — composable boolean domain rules."""

from __future__ import annotations

import abc
from typing import Generic, TypeVar

T = TypeVar("T")


class BaseSpecification(abc.ABC, Generic[T]):
    """Abstract base for specifications — provides operator overloads.

    Subclass this (or ``Specification``) and implement ``is_satisfied_by``.

    Example::

        class ActiveUser(BaseSpecification[User]):
            def is_satisfied_by(self, candidate: User) -> bool:
                return candidate.is_active

        spec = ActiveUser() & HasVerifiedEmail()
    """

    @abc.abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool: ...

    # Named combinators ------------------------------------------------
    def and_(self, other: "BaseSpecification[T]") -> "AndSpecification[T]":
        return AndSpecification(self, other)

    def or_(self, other: "BaseSpecification[T]") -> "OrSpecification[T]":
        return OrSpecification(self, other)

    def not_(self) -> "NotSpecification[T]":
        return NotSpecification(self)

    # Operator overloads -----------------------------------------------
    def __and__(self, other: "BaseSpecification[T]") -> "AndSpecification[T]":
        return AndSpecification(self, other)

    def __or__(self, other: "BaseSpecification[T]") -> "OrSpecification[T]":
        return OrSpecification(self, other)

    def __invert__(self) -> "NotSpecification[T]":
        return NotSpecification(self)


# Keep the old Protocol name as an alias for backwards-compatibility
Specification = BaseSpecification  # type: ignore[misc]


class AndSpecification(BaseSpecification[T]):
    """Conjunction of two specifications."""

    def __init__(self, left: BaseSpecification[T], right: BaseSpecification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)


class OrSpecification(BaseSpecification[T]):
    """Disjunction of two specifications."""

    def __init__(self, left: BaseSpecification[T], right: BaseSpecification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)


class NotSpecification(BaseSpecification[T]):
    """Negation of a specification."""

    def __init__(self, spec: BaseSpecification[T]) -> None:
        self._spec = spec

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self._spec.is_satisfied_by(candidate)


__all__ = [
    "AndSpecification",
    "BaseSpecification",
    "NotSpecification",
    "OrSpecification",
    "Specification",
]
