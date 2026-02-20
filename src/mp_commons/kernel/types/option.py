"""Option[T] monad — Some and Nothing variants."""

from __future__ import annotations

from typing import Callable, Generic, Iterator, NoReturn, TypeVar

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
        return True

    def is_none(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self._value

    def unwrap_or(self, default: T) -> T:  # noqa: ARG002
        return self._value

    def map(self, func: Callable[[T], T]) -> "Some[T]":
        return Some(func(self._value))

    def __iter__(self) -> Iterator[T]:
        yield self._value

    def __repr__(self) -> str:
        return f"Some({self._value!r})"


class Nothing(Generic[T]):
    """Empty option."""

    __slots__ = ()

    def is_some(self) -> bool:
        return False

    def is_none(self) -> bool:
        return True

    def unwrap(self) -> NoReturn:
        raise ValueError("Called unwrap() on Nothing")

    def unwrap_or(self, default: T) -> T:
        return default

    def map(self, func: Callable[[T], T]) -> "Nothing[T]":  # noqa: ARG002
        return self

    def __iter__(self) -> Iterator[T]:
        return iter(())

    def __repr__(self) -> str:
        return "Nothing"


type Option[T] = Some[T] | Nothing[T]

__all__ = ["Nothing", "Option", "Some"]
