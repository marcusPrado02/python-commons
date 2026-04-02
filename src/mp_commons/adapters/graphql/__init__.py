"""GraphQL adapter — Relay-style cursor pagination and error handler.

For Strawberry-GraphQL integration install ``strawberry-graphql>=0.220``.
The cursor utilities and error handler work without Strawberry.
"""

from __future__ import annotations

from mp_commons.adapters.graphql.pagination import (
    CursorConnection,
    Edge,
    PageInfo,
    decode_cursor,
    encode_cursor,
    graphql_error_handler,
)

__all__ = [
    "CursorConnection",
    "Edge",
    "PageInfo",
    "decode_cursor",
    "encode_cursor",
    "graphql_error_handler",
]
