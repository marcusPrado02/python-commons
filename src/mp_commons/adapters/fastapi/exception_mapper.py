"""FastAPI adapter – FastAPIExceptionMapper."""
from __future__ import annotations

from typing import Any, Callable


def _require_fastapi() -> None:
    try:
        import fastapi  # noqa: F401
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[fastapi]' to use the FastAPI adapter") from exc


class FastAPIExceptionMapper:
    """Register mp_commons error → HTTP status code mappings on a FastAPI app."""

    def __init__(self) -> None:
        _require_fastapi()
        from mp_commons.kernel.errors import (
            ConflictError, ForbiddenError, NotFoundError,
            RateLimitError, TimeoutError, UnauthorizedError, ValidationError,
        )
        self._map: dict[type[Exception], int] = {
            ValidationError: 422,
            NotFoundError: 404,
            ConflictError: 409,
            UnauthorizedError: 401,
            ForbiddenError: 403,
            RateLimitError: 429,
            TimeoutError: 504,
        }

    def register(self, app: Any) -> None:
        """Register all error handlers on a ``FastAPI`` or ``Starlette`` app."""
        from fastapi.responses import JSONResponse  # type: ignore[import-untyped]
        from mp_commons.kernel.errors import BaseError

        for exc_type, status in self._map.items():

            def make_handler(code: int) -> Callable[[Any, Any], Any]:
                def handler(request: Any, exc: Any) -> Any:  # noqa: ARG001
                    if isinstance(exc, BaseError):
                        return JSONResponse(status_code=code, content=exc.to_dict())
                    return JSONResponse(status_code=code, content={"code": "error", "message": str(exc)})
                return handler

            app.add_exception_handler(exc_type, make_handler(status))


__all__ = ["FastAPIExceptionMapper"]
