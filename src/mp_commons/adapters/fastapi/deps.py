"""FastAPI adapter – reusable dependency functions.

§26.8  FastAPIPaginationDep
§26.10 openapi_extra helpers
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

if TYPE_CHECKING:
    pass


def _require_fastapi() -> None:
    try:
        import fastapi  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Install 'mp-commons[fastapi]' to use the FastAPI adapter"
        ) from exc


# ---------------------------------------------------------------------------
# §26.8 – Pagination dependency
# ---------------------------------------------------------------------------

def _pagination_dep_factory():  # noqa: ANN202
    """Return the ``pagination_dep`` async function bound to FastAPI Depends."""
    _require_fastapi()
    from fastapi import Query  # type: ignore[import-untyped]
    from mp_commons.application.pagination.page_request import PageRequest

    async def pagination_dep(
        page: int = Query(default=1, ge=1, description="1-based page number"),
        size: int = Query(default=20, ge=1, le=1000, description="Items per page"),
        sort_by: str | None = Query(default=None, description="Field to sort by"),
        sort_dir: Literal["asc", "desc"] = Query(default="asc", description="Sort direction"),
    ) -> PageRequest:
        """Extract and validate pagination parameters from query string."""
        sorts: tuple[str, ...] = ()
        if sort_by:
            prefix = "" if sort_dir == "asc" else "-"
            sorts = (f"{prefix}{sort_by}",)
        return PageRequest(page=page, size=size, sorts=sorts)

    return pagination_dep


def _make_pagination_dep():  # noqa: ANN202
    """Create ``FastAPIPaginationDep`` type alias, importing lazily."""
    try:
        from fastapi import Depends  # type: ignore[import-untyped]
        from mp_commons.application.pagination.page_request import PageRequest
        fn = _pagination_dep_factory()
        return Annotated[PageRequest, Depends(fn)]
    except ImportError:
        return None


# Build at import time (no-op if fastapi absent)
FastAPIPaginationDep = _make_pagination_dep()


# ---------------------------------------------------------------------------
# §26.10 – OpenAPI extra helpers
# ---------------------------------------------------------------------------

_ERROR_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "message": {"type": "string"},
        "correlation_id": {"type": "string", "nullable": True},
    },
    "required": ["code", "message"],
}

_DEFAULT_STATUS_DESCRIPTIONS: dict[int, str] = {
    400: "Validation error",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Resource not found",
    409: "Conflict",
    422: "Domain rule violated",
    429: "Rate limit exceeded",
    500: "Internal server error",
    503: "Service unavailable",
    504: "Upstream timeout",
}


def error_responses(*codes: int) -> dict[int | str, dict[str, object]]:
    """Build an ``openapi_extra[\"responses\"]`` dict for the given HTTP codes.

    Usage::

        @router.post(
            "/widgets",
            openapi_extra=error_responses(400, 404, 409),
        )
        async def create_widget(...): ...
    """
    result: dict[int | str, dict[str, object]] = {}
    for code in codes:
        description = _DEFAULT_STATUS_DESCRIPTIONS.get(code, "Error")
        result[str(code)] = {
            "description": description,
            "content": {
                "application/json": {
                    "schema": _ERROR_SCHEMA,
                    "example": {
                        "code": _code_for_status(code),
                        "message": description,
                        "correlation_id": "00000000-0000-0000-0000-000000000000",
                    },
                }
            },
        }
    return result


def _code_for_status(status: int) -> str:
    mapping = {
        400: "validation_error",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "domain_error",
        429: "rate_limit_exceeded",
        500: "internal_error",
        503: "service_unavailable",
        504: "timeout",
    }
    return mapping.get(status, "error")


__all__ = [
    "FastAPIPaginationDep",
    "error_responses",
]
