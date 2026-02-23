"""SQLAlchemy ORM mixins – TimestampMixin, SoftDeleteMixin (§27.8 / §27.9)."""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import declared_attr, mapped_column, Mapped


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` timestamp columns.

    Mix into any concrete ORM model class that extends
    :class:`~sqlalchemy.orm.DeclarativeBase`::

        class Order(TimestampMixin, Base):
            __tablename__ = "orders"
            id: Mapped[int] = mapped_column(primary_key=True)

    Both columns default to the current UTC time managed by the *database*
    server (``server_default=func.now()``).  ``updated_at`` is refreshed
    automatically on every UPDATE via ``onupdate=func.now()``.
    """

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Adds a ``deleted_at`` nullable timestamp column for soft-deletion.

    Usage::

        class Product(SoftDeleteMixin, Base):
            __tablename__ = "products"
            id: Mapped[int] = mapped_column(primary_key=True)

    ``deleted_at`` is ``NULL`` for live rows and set to a UTC timestamp
    when soft-deleted.

    Helper
    ------
    :meth:`not_deleted_filter` returns the SQLAlchemy column expression
    ``deleted_at IS NULL`` — useful in WHERE clauses::

        # inside a query
        stmt = select(Product).where(Product.not_deleted_filter())
    """

    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )

    @classmethod
    def not_deleted_filter(cls) -> Any:
        """Return a column expression ``<cls>.deleted_at IS NULL``."""
        return cls.deleted_at.is_(None)  # type: ignore[attr-defined]

    def soft_delete(self) -> None:
        """Mark this row as deleted by setting ``deleted_at`` to now (UTC)."""
        self.deleted_at = datetime.datetime.now(datetime.UTC)  # type: ignore[assignment]

    @property
    def is_deleted(self) -> bool:
        """``True`` if this row has been soft-deleted."""
        return self.deleted_at is not None  # type: ignore[attr-defined]


__all__ = ["SoftDeleteMixin", "TimestampMixin"]
