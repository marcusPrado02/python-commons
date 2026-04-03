"""Unit tests for the GraphQL adapter (§52)."""

from __future__ import annotations

import pytest

from mp_commons.adapters.graphql.pagination import (
    CursorConnection,
    decode_cursor,
    encode_cursor,
    graphql_error_handler,
)

# ---------------------------------------------------------------------------
# Cursor encode / decode round-trip
# ---------------------------------------------------------------------------


def test_encode_decode_round_trip():
    for offset in [0, 1, 42, 1000]:
        assert decode_cursor(encode_cursor(offset)) == offset


def test_cursor_is_opaque():
    cursor = encode_cursor(5)
    assert "5" not in cursor  # must not be plaintext


def test_cursor_different_offsets_differ():
    assert encode_cursor(0) != encode_cursor(1)


def test_decode_invalid_cursor_raises():
    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_cursor("not-a-valid-cursor")


def test_decode_corrupted_base64_raises():
    with pytest.raises(ValueError):
        decode_cursor("!!!!")


# ---------------------------------------------------------------------------
# CursorConnection
# ---------------------------------------------------------------------------


def test_connection_builds_edges():
    conn = CursorConnection.from_list(["a", "b", "c"], total_count=10, offset=0, limit=3)
    assert len(conn.edges) == 3
    assert conn.edges[0].node == "a"
    assert conn.edges[2].node == "c"


def test_connection_cursors_use_offset():
    conn = CursorConnection.from_list(["x", "y"], total_count=5, offset=3, limit=2)
    assert decode_cursor(conn.edges[0].cursor) == 3
    assert decode_cursor(conn.edges[1].cursor) == 4


def test_connection_page_info_has_next():
    conn = CursorConnection.from_list(["a"], total_count=10, offset=0, limit=1)
    assert conn.page_info.has_next_page is True


def test_connection_page_info_no_next():
    conn = CursorConnection.from_list(["a"], total_count=1, offset=0, limit=1)
    assert conn.page_info.has_next_page is False


def test_connection_page_info_has_previous():
    conn = CursorConnection.from_list(["b"], total_count=5, offset=2, limit=1)
    assert conn.page_info.has_previous_page is True


def test_connection_page_info_no_previous():
    conn = CursorConnection.from_list(["a"], total_count=5, offset=0, limit=1)
    assert conn.page_info.has_previous_page is False


def test_connection_end_cursor():
    conn = CursorConnection.from_list(["p", "q"], total_count=5, offset=1, limit=2)
    assert conn.page_info.end_cursor == encode_cursor(2)


def test_connection_empty_list():
    conn = CursorConnection.from_list([], total_count=0, offset=0, limit=10)
    assert conn.edges == []
    assert conn.page_info.start_cursor is None
    assert conn.page_info.end_cursor is None
    assert conn.page_info.has_next_page is False


def test_connection_total_count():
    conn = CursorConnection.from_list(["a"], total_count=99, offset=0, limit=1)
    assert conn.total_count == 99


# ---------------------------------------------------------------------------
# graphql_error_handler
# ---------------------------------------------------------------------------


from mp_commons.kernel.errors.domain import ConflictError, NotFoundError, ValidationError


def test_error_handler_not_found():
    exc = NotFoundError("User not found")
    result = graphql_error_handler(exc)
    assert result["extensions"]["code"] == "NOT_FOUND"
    assert "User not found" in result["message"]


def test_error_handler_conflict():
    exc = ConflictError("Email already exists")
    result = graphql_error_handler(exc)
    assert result["extensions"]["code"] == "CONFLICT"


def test_error_handler_validation():
    exc = ValidationError("field required")
    result = graphql_error_handler(exc)
    assert result["extensions"]["code"] == "VALIDATION_ERROR"


def test_error_handler_generic():
    exc = RuntimeError("something unexpected")
    result = graphql_error_handler(exc)
    assert result["extensions"]["code"] == "INTERNAL_ERROR"
