"""Specification pattern — composable boolean domain rules."""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

T = TypeVar("T")


class Specification(Protocol[T]):
    """Boolean rule that determines if a candidate satisfies a criterion."""

    def is_satisfied_by(self, candidate: T) -> bool: ...

    def and_(self, other: "Specification[T]") -> "AndSpecification[T]":
        return AndSpecification(self, other)

    def or_(self, other: "Specification[T]") -> "OrSpecification[T]":
        return OrSpecification(self, other)

    def not_(self) -> "NotSpecification[T]":
        return NotSpecification(self)


class AndSpecification(Generic[T]):
    """Conjunction of two specifications."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)

    def and_(self, other: Specification[T]) -> "AndSpecification[T]":
        return AndSpecification(self, other)

    def or_(self, other: Specification[T]) -> "OrSpecification[T]":
        return OrSpecification(self, other)

    def not_(self) -> "NotSpecification[T]":
        return NotSpecification(self)


class OrSpecification(Generic[T]):
    """Disjunction of two specifications."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)

    def and_(self, other: Specification[T]) -> AndSpecification[T]:
        return AndSpecification(self, other)

    def or_(self, other: Specification[T]) -> "OrSpecification[T]":
        return OrSpecification(self, other)

    def not_(self) -> "NotSpecification[T]":
        return NotSpecification(self)


class NotSpecification(Generic[T]):
    """Negation of a specification."""

    def __init__(self, spec: Specification[T]) -> None:
        self._spec = spec

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self._spec.is_satisfied_by(candidate)

    def and_(self, other: Specification[T]) -> AndSpecification[T]:
        return AndSpecification(self, other)

    def or_(self, other: Specification[T]) -> OrSpecification[T]:
        return OrSpecification(self, other)

    def not_(self) -> "NotSpecification[T]":
        return NotSpecification(self)


__all__ = [
    "AndSpecification",
    "NotSpecification",
    "OrSpecification",
    "Specification",
]
