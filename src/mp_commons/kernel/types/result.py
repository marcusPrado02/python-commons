"""Result[T, E] monad — Ok and Err variants."""

from __future__ import annotations

from typing import Callable, Generic, Iterator, NoReturn, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound=Exception)


class Ok(Generic[T]):
    """Successful result variant."""

    __slots__ = ("_value",)

    def __init__(self, value: T) -> None:
        self._value = value

    @property
    def value(self) -> T:
        return self._value

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self._value

    def unwrap_or(self, default: T) -> T:  # noqa: ARG002
        return self._value

    def map(self, func: Callable[[T], "T"]) -> "Ok[T]":
        return Ok(func(self._value))

    def flat_map(self, func: "Callable[[T], Result[T, E]]"  ) -> "Result[T, E]":
        return func(self._value)

    def __repr__(self) -> str:
        return f"Ok({self._value!r})"


class Err(Generic[E]):
    """Error result variant."""

    __slots__ = ("_error",)

    def __init__(self, error: E) -> None:
        self._error = error

    @property
    def error(self) -> E:
        return self._error

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> NoReturn:
        raise self._error

    def unwrap_or(self, default: T) -> T:
        return default

    def map(self, func: Callable[[T], T]) -> "Err[E]":  # noqa: ARG002
        return self

    def flat_map(self, func: "Callable[[T], Result[T, E]]"  ) -> "Err[E]":  # noqa: ARG002
        return self

    def __repr__(self) -> str:
        return f"Err({self._error!r})"


type Result[T, E] = Ok[T] | Err[E]

__all__ = ["Err", "Ok", "Result"]
