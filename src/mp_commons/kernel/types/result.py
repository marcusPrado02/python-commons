"""Result[T, E] monad — Ok and Err variants."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, NoReturn, TypeVar

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
        """Return ``True`` — this is a successful result."""
        return True

    def is_err(self) -> bool:
        """Return ``False`` — this is not an error."""
        return False

    def unwrap(self) -> T:
        """Return the contained value."""
        return self._value

    def unwrap_or(self, default: T) -> T:
        """Return the contained value, ignoring *default*."""
        return self._value

    def map(self, func: Callable[[T], T]) -> Ok[T]:
        """Apply *func* to the value and wrap the result in a new ``Ok``."""
        return Ok(func(self._value))

    def flat_map(self, func: Callable[[T], Result[T, E]]) -> Result[T, E]:
        """Apply *func* (which returns a ``Result``) to the contained value."""
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
        """Return ``False`` — this is an error result."""
        return False

    def is_err(self) -> bool:
        """Return ``True`` — this is an error."""
        return True

    def unwrap(self) -> NoReturn:
        """Raise the contained error."""
        raise self._error

    def unwrap_or(self, default: T) -> T:
        """Return *default* because this result is an error."""
        return default

    def map(self, func: Callable[[T], T]) -> Err[E]:
        """Return ``self`` unchanged — mapping over an error is a no-op."""
        return self

    def flat_map(self, func: Callable[[T], Result[T, E]]) -> Err[E]:
        """Return ``self`` unchanged — chaining over an error is a no-op."""
        return self

    def __repr__(self) -> str:
        return f"Err({self._error!r})"


type Result[T, E] = Ok[T] | Err[E]

__all__ = ["Err", "Ok", "Result"]
