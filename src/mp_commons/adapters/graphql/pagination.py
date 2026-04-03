"""GraphQL utilities — Relay-style cursor pagination and error mapping.

Cursor encoding uses opaque base64-encoded integers (offset-based).
All utilities are pure Python with no Strawberry dependency.
"""

from __future__ import annotations

import base64
import dataclasses
from typing import Any, Generic, TypeVar

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------

_PREFIX = "cursor:"


def encode_cursor(offset: int) -> str:
    """Encode an integer offset into an opaque, URL-safe base64 cursor string."""
    raw = f"{_PREFIX}{offset}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> int:
    """Decode an opaque cursor back to its integer offset.

    Raises :class:`ValueError` if the cursor is malformed.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode()
        if not raw.startswith(_PREFIX):
            raise ValueError(f"Invalid cursor: {cursor!r}")
        return int(raw[len(_PREFIX) :])
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {cursor!r}") from exc


# ---------------------------------------------------------------------------
# Relay connection types
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PageInfo:
    """Relay PageInfo object."""

    has_next_page: bool
    has_previous_page: bool
    start_cursor: str | None
    end_cursor: str | None


@dataclasses.dataclass(frozen=True)
class Edge(Generic[T]):
    """A single edge in a Relay connection."""

    node: T
    cursor: str


@dataclasses.dataclass(frozen=True)
class CursorConnection(Generic[T]):
    """Relay-style cursor connection.

    Build via :meth:`from_list` for simple offset-based pagination.
    """

    edges: list[Edge[T]]
    page_info: PageInfo
    total_count: int

    @classmethod
    def from_list(
        cls,
        items: list[T],
        total_count: int,
        *,
        offset: int = 0,
        limit: int = 10,
    ) -> CursorConnection[T]:
        """Create a connection from a pre-sliced *items* list.

        Parameters
        ----------
        items:
            The page of nodes (already sliced to at most *limit* items).
        total_count:
            Total number of records matching the query (before pagination).
        offset:
            Zero-based offset of the first item in *items*.
        limit:
            Page size requested.
        """
        edges = [Edge(node=node, cursor=encode_cursor(offset + i)) for i, node in enumerate(items)]
        start_cursor = edges[0].cursor if edges else None
        end_cursor = edges[-1].cursor if edges else None
        has_next_page = (offset + len(items)) < total_count
        has_previous_page = offset > 0
        return cls(
            edges=edges,
            page_info=PageInfo(
                has_next_page=has_next_page,
                has_previous_page=has_previous_page,
                start_cursor=start_cursor,
                end_cursor=end_cursor,
            ),
            total_count=total_count,
        )


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


def graphql_error_handler(exc: Exception) -> dict[str, Any]:
    """Map a domain exception to a GraphQL-compatible error extension dict.

    Returns a dict with ``message``, ``extensions.code``, and optional
    ``extensions.fields`` for validation errors.  Callers can raise a
    Strawberry ``GraphQLError`` with ``extensions`` set to the returned value.

    Supported domain exceptions
    ---------------------------
    * :class:`~mp_commons.kernel.errors.domain.NotFoundError` → ``NOT_FOUND``
    * :class:`~mp_commons.kernel.errors.domain.ConflictError` → ``CONFLICT``
    * :class:`~mp_commons.kernel.errors.domain.ValidationError` → ``VALIDATION_ERROR``
    * Any other ``Exception`` → ``INTERNAL_ERROR``
    """
    from mp_commons.kernel.errors.domain import ConflictError, NotFoundError, ValidationError

    code: str
    extensions: dict[str, Any] = {}

    if isinstance(exc, NotFoundError):
        code = "NOT_FOUND"
    elif isinstance(exc, ConflictError):
        code = "CONFLICT"
    elif isinstance(exc, ValidationError):
        code = "VALIDATION_ERROR"
        if hasattr(exc, "fields"):
            extensions["fields"] = exc.fields  # type: ignore[attr-defined]
    else:
        code = "INTERNAL_ERROR"

    return {
        "message": str(exc),
        "extensions": {"code": code, **extensions},
    }


__all__ = [
    "CursorConnection",
    "Edge",
    "PageInfo",
    "decode_cursor",
    "encode_cursor",
    "graphql_error_handler",
]
