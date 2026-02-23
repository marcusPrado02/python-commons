"""Testing generators – Builder[T] generic fluent builder base."""
from __future__ import annotations

import copy
import dataclasses
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Builder(Generic[T]):
    """Generic fluent builder base for constructing test domain objects.

    Sub-class and override :meth:`build` to return the target type::

        class OrderBuilder(Builder[Order]):
            def __init__(self) -> None:
                super().__init__()
                self._attrs = {
                    "order_id": "ord-123",
                    "amount": 100,
                    "status": "pending",
                }

            def build(self) -> Order:
                return Order(**self._attrs)

    Each ``with_*`` call returns a **new** builder instance so the original
    remains unchanged (immutable builder pattern)::

        base = OrderBuilder()
        paid   = base.with_(status="paid")
        failed = base.with_(status="failed")
    """

    def __init__(self) -> None:
        self._attrs: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Fluent API
    # ------------------------------------------------------------------

    def with_(self, **kwargs: Any) -> "Builder[T]":
        """Return a shallow copy of this builder with *kwargs* applied."""
        clone = copy.copy(self)
        clone._attrs = {**self._attrs, **kwargs}  # noqa: SLF001
        return clone

    def override(self, key: str, value: Any) -> "Builder[T]":
        """Single-key variant of :meth:`with_`."""
        return self.with_(**{key: value})

    # ------------------------------------------------------------------
    # Attributes access
    # ------------------------------------------------------------------

    @property
    def attrs(self) -> dict[str, Any]:
        """Return a snapshot of the current attribute dict."""
        return dict(self._attrs)

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value of *key*, or *default* if not set."""
        return self._attrs.get(key, default)

    # ------------------------------------------------------------------
    # Buildable
    # ------------------------------------------------------------------

    def build(self) -> T:  # type: ignore[misc]
        """Construct and return the target object.  Must be overridden."""
        raise NotImplementedError(  # pragma: no cover
            f"{type(self).__name__}.build() is not implemented"
        )

    # Alias: makes builders usable as callables, e.g. ``OrderBuilder()()``
    def __call__(self, **overrides: Any) -> T:
        if overrides:
            return self.with_(**overrides).build()
        return self.build()


class DataclassBuilder(Builder[T]):
    """Convenience builder for *dataclass* targets.

    Set ``_cls`` on the subclass and provide defaults in ``__init__``::

        @dataclasses.dataclass
        class Point:
            x: float
            y: float

        class PointBuilder(DataclassBuilder[Point]):
            _cls = Point

            def __init__(self) -> None:
                super().__init__()
                self._attrs = {"x": 0.0, "y": 0.0}

    ``build()`` calls ``_cls(**self._attrs)`` automatically.
    """

    _cls: type[T]

    def build(self) -> T:
        return self._cls(**self._attrs)  # type: ignore[call-arg]


__all__ = ["Builder", "DataclassBuilder"]
