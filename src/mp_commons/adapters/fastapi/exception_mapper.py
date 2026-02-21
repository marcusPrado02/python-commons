"""FastAPI adapter – FastAPIExceptionMapper (§26.4)."""
from __future__ import annotations

from typing import Any, Callable


def _require_fastapi() -> None:
    try:
        import fastapi  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Install 'mp-commons[fastapi]' to use the FastAPI adapter"
        ) from exc


class FastAPIExceptionMapper:
    """Register mp_commons error → HTTP status-code mappings on a FastAPI app.

    Error body schema::

        {"code": "not_found", "message": "...", "correlation_id": "..."}

    Mappings
    --------
    ``DomainError``         → 422
    ``ValidationError``     → 400
    ``NotFoundError``       → 404
    ``ConflictError``       → 409
    ``UnauthorizedError``   → 401
    ``ForbiddenError``      → 403
    ``RateLimitError``      → 429
    ``TimeoutError``        → 504
    ``InfrastructureError`` → 503
    """

    def __init__(self) -> None:
        _require_fastapi()
        from mp_commons.kernel.errors import (
            ConflictError,
            DomainError,
            ForbiddenError,
            InfrastructureError,
            NotFoundError,
            RateLimitError,
            TimeoutError,
            UnauthorizedError,
            ValidationError,
        )

        # ORDER MATTERS: more-specific subtypes first
        self._map: list[tuple[type[Exception], int]] = [
            (ValidationError, 400),
            (NotFoundError, 404),
            (ConflictError, 409),
            (UnauthorizedError, 401),
            (ForbiddenError, 403),
            (RateLimitError, 429),
            (TimeoutError, 504),
            (InfrastructureError, 503),
            (DomainError, 422),
        ]

    def register(self, app: Any) -> None:
        """Register all error handlers on a ``FastAPI`` or ``Starlette`` app."""
        from fastapi.responses import JSONResponse  # type: ignore[import-untyped]

        for exc_type, status in self._map:

            def make_handler(code: int, etype: type) -> Callable[[Any, Any], Any]:
                def handler(request: Any, exc: Any) -> Any:  # noqa: ARG001
                    from mp_commons.kernel.errors.base import BaseError
                    from mp_commons.observability.correlation import CorrelationContext

                    correlation_id: str | None = None
                    ctx = CorrelationContext.get()
                    if ctx is not None:
                        correlation_id = ctx.correlation_id

                    if isinstance(exc, BaseError):
                        body = exc.to_dict()
                    else:
                        body = {"code": "error", "message": str(exc)}

                    body["correlation_id"] = correlation_id
                    return JSONResponse(status_code=code, content=body)

                return handler

            app.add_exception_handler(exc_type, make_handler(status, exc_type))


__all__ = ["FastAPIExceptionMapper"]
