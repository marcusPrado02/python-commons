"""Option[T] monad — Some and Nothing variants."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Generic, NoReturn, TypeVar

T = TypeVar("T")


class Some(Generic[T]):
    """Option with a value."""

    __slots__ = ("_value",)

    def __init__(self, value: T) -> None:
        self._value = value

    @property
    def value(self) -> T:
        return self._value

    def is_some(self) -> bool:
        """Return ``True`` — a value is present."""
        return True

    def is_none(self) -> bool:
        """Return ``False`` — this option is not empty."""
        return False

    def unwrap(self) -> T:
        """Return the contained value."""
        return self._value

    def unwrap_or(self, default: T) -> T:
        """Return the contained value, ignoring *default*."""
        return self._value

    def map(self, func: Callable[[T], T]) -> Some[T]:
        """Apply *func* to the value and wrap the result in a new ``Some``."""
        return Some(func(self._value))

    def flat_map(self, func: Callable[[T], Option[T]]) -> Option[T]:
        """Apply *func* (which returns an ``Option``) to the contained value."""
        return func(self._value)

    def filter(self, predicate: Callable[[T], bool]) -> Option[T]:
        """Return ``self`` if *predicate* holds, otherwise ``Nothing``."""
        return self if predicate(self._value) else Nothing()

    def __iter__(self) -> Iterator[T]:
        yield self._value

    def __repr__(self) -> str:
        return f"Some({self._value!r})"


class Nothing(Generic[T]):
    """Empty option."""

    __slots__ = ()

    def is_some(self) -> bool:
        """Return ``False`` — no value is present."""
        return False

    def is_none(self) -> bool:
        """Return ``True`` — this option is empty."""
        return True

    def unwrap(self) -> NoReturn:
        """Raise ``ValueError`` — cannot unwrap an empty option."""
        raise ValueError("Called unwrap() on Nothing")

    def unwrap_or(self, default: T) -> T:
        """Return *default* because no value is present."""
        return default

    def map(self, func: Callable[[T], T]) -> Nothing[T]:
        """Return ``self`` unchanged — mapping over Nothing is a no-op."""
        return self

    def flat_map(self, func: Callable[[T], Option[T]]) -> Nothing[T]:
        """Return ``self`` unchanged — chaining over Nothing is a no-op."""
        return self

    def filter(self, predicate: Callable[[T], bool]) -> Nothing[T]:
        """Return ``self`` unchanged — filtering Nothing always yields Nothing."""
        return self

    def __iter__(self) -> Iterator[T]:
        return iter(())

    def __repr__(self) -> str:
        return "Nothing"


type Option[T] = Some[T] | Nothing[T]

__all__ = ["Nothing", "Option", "Some"]
