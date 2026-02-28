"""SQLAlchemy Specification mixin — §58.4.

Provides :class:`SQLAlchemySpecification` which extends the kernel
:class:`~mp_commons.kernel.ddd.specification.BaseSpecification` with a
``to_expression()`` method returning a SQLAlchemy ``ColumnElement`` for use
inside ``WHERE`` clauses.

Example::

    from sqlalchemy import Column, String, select
    from mp_commons.adapters.sqlalchemy.specification import SQLAlchemySpecification

    class ActiveUserSpec(SQLAlchemySpecification[User]):
        def is_satisfied_by(self, candidate: User) -> bool:
            return candidate.is_active

        def to_expression(self):
            return User.is_active.is_(True)

    stmt = select(User).where(ActiveUserSpec().to_expression())

Composite specifications produced by ``&`` / ``|`` / ``~`` also expose
``to_expression`` so the entire expression tree can be converted to SQL.

Requires ``sqlalchemy>=2.0``.
"""
from __future__ import annotations

import abc
from typing import Any, Generic, TypeVar

from mp_commons.kernel.ddd.specification import (
    AndSpecification,
    BaseSpecification,
    NotSpecification,
    OrSpecification,
)

T = TypeVar("T")

# Type alias for SQLAlchemy ColumnElement (avoid hard import at module level)
_ColumnElement = Any


class SQLAlchemySpecification(BaseSpecification[T], abc.ABC, Generic[T]):
    """Specification that can produce a SQLAlchemy WHERE expression.

    Subclasses must implement both :meth:`is_satisfied_by` (in-memory
    evaluation) and :meth:`to_expression` (SQL expression).

    The ``&``, ``|``, and ``~`` operators are overloaded to produce
    :class:`SQLAlchemyAndSpecification`, :class:`SQLAlchemyOrSpecification`,
    and :class:`SQLAlchemyNotSpecification` respectively, all of which also
    implement ``to_expression``.
    """

    @abc.abstractmethod
    def to_expression(self) -> _ColumnElement:
        """Return a SQLAlchemy ``ColumnElement`` suitable for ``where()``."""

    # Override combinators to return SQLAlchemy-aware composites ----------

    def __and__(self, other: "BaseSpecification[T]") -> "SQLAlchemyAndSpecification[T]":
        return SQLAlchemyAndSpecification(self, other)

    def __or__(self, other: "BaseSpecification[T]") -> "SQLAlchemyOrSpecification[T]":
        return SQLAlchemyOrSpecification(self, other)

    def __invert__(self) -> "SQLAlchemyNotSpecification[T]":
        return SQLAlchemyNotSpecification(self)


# ---------------------------------------------------------------------------
# SQL-aware composite specifications
# ---------------------------------------------------------------------------


class SQLAlchemyAndSpecification(AndSpecification[T]):
    """AND composite that also exposes ``to_expression``."""

    def to_expression(self) -> _ColumnElement:
        from sqlalchemy import and_  # type: ignore[import-untyped]

        left_expr = _get_expression(self._left)
        right_expr = _get_expression(self._right)
        return and_(left_expr, right_expr)

    def __and__(self, other: "BaseSpecification[T]") -> "SQLAlchemyAndSpecification[T]":
        return SQLAlchemyAndSpecification(self, other)

    def __or__(self, other: "BaseSpecification[T]") -> "SQLAlchemyOrSpecification[T]":
        return SQLAlchemyOrSpecification(self, other)

    def __invert__(self) -> "SQLAlchemyNotSpecification[T]":
        return SQLAlchemyNotSpecification(self)


class SQLAlchemyOrSpecification(OrSpecification[T]):
    """OR composite that also exposes ``to_expression``."""

    def to_expression(self) -> _ColumnElement:
        from sqlalchemy import or_  # type: ignore[import-untyped]

        left_expr = _get_expression(self._left)
        right_expr = _get_expression(self._right)
        return or_(left_expr, right_expr)

    def __and__(self, other: "BaseSpecification[T]") -> "SQLAlchemyAndSpecification[T]":
        return SQLAlchemyAndSpecification(self, other)

    def __or__(self, other: "BaseSpecification[T]") -> "SQLAlchemyOrSpecification[T]":
        return SQLAlchemyOrSpecification(self, other)

    def __invert__(self) -> "SQLAlchemyNotSpecification[T]":
        return SQLAlchemyNotSpecification(self)


class SQLAlchemyNotSpecification(NotSpecification[T]):
    """NOT composite that also exposes ``to_expression``."""

    def to_expression(self) -> _ColumnElement:
        from sqlalchemy import not_  # type: ignore[import-untyped]

        inner_expr = _get_expression(self._spec)
        return not_(inner_expr)

    def __and__(self, other: "BaseSpecification[T]") -> "SQLAlchemyAndSpecification[T]":
        return SQLAlchemyAndSpecification(self, other)

    def __or__(self, other: "BaseSpecification[T]") -> "SQLAlchemyOrSpecification[T]":
        return SQLAlchemyOrSpecification(self, other)

    def __invert__(self) -> "SQLAlchemyNotSpecification[T]":
        return SQLAlchemyNotSpecification(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_expression(spec: "BaseSpecification[Any]") -> _ColumnElement:
    """Retrieve a SQL expression from *spec*, raising if unsupported."""
    if hasattr(spec, "to_expression"):
        return spec.to_expression()  # type: ignore[attr-defined]
    raise TypeError(
        f"Specification {type(spec).__name__!r} does not implement "
        "to_expression(). Wrap it in an SQLAlchemySpecification subclass."
    )


__all__ = [
    "SQLAlchemyAndSpecification",
    "SQLAlchemyNotSpecification",
    "SQLAlchemyOrSpecification",
    "SQLAlchemySpecification",
]
