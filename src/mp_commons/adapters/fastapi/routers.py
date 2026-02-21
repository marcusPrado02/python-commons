"""FastAPI adapter – health / metrics routers (§26.5)."""
from __future__ import annotations

from typing import Any, Awaitable, Callable


def _require_fastapi() -> None:
    try:
        import fastapi  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Install 'mp-commons[fastapi]' to use the FastAPI adapter"
        ) from exc


ReadinessCheck = Callable[[], Awaitable[bool]]


def FastAPIHealthRouter(
    path: str = "/health",
    readiness_checks: list[ReadinessCheck] | None = None,
    tags: list[str] | None = None,
) -> Any:
    """Return a liveness + readiness health-check router.

    Parameters
    ----------
    path:
        Base path prefix.  Liveness is at ``{path}/live``, readiness at
        ``{path}/ready``.
    readiness_checks:
        Optional list of async callables returning ``bool``.  All checks
        must return ``True`` for the readiness endpoint to return 200;
        otherwise it returns 503.
    tags:
        OpenAPI tags for the generated routes.
    """
    _require_fastapi()
    from fastapi import APIRouter  # type: ignore[import-untyped]
    from fastapi.responses import JSONResponse  # type: ignore[import-untyped]

    router = APIRouter(tags=tags or ["ops"])
    checks = readiness_checks or []

    @router.get(f"{path}/live")
    async def liveness() -> dict[str, str]:
        """Kubernetes liveness probe – always 200 OK when the process is up."""
        return {"status": "ok"}

    @router.get(f"{path}/ready")
    async def readiness() -> Any:
        """Kubernetes readiness probe – runs all registered readiness checks."""
        results: dict[str, bool] = {}
        all_ok = True
        for check in checks:
            name = getattr(check, "__name__", repr(check))
            try:
                ok = await check()
            except Exception:  # noqa: BLE001
                ok = False
            results[name] = ok
            if not ok:
                all_ok = False

        status_code = 200 if all_ok else 503
        return JSONResponse(
            status_code=status_code,
            content={"status": "ok" if all_ok else "degraded", "checks": results},
        )

    return router


def FastAPIMetricsRouter(path: str = "/metrics") -> Any:
    """Return a Prometheus metrics router (requires prometheus-client)."""
    _require_fastapi()
    from fastapi import APIRouter  # type: ignore[import-untyped]
    from fastapi.responses import PlainTextResponse  # type: ignore[import-untyped]

    router = APIRouter()

    @router.get(path, tags=["ops"], response_class=PlainTextResponse)
    async def metrics() -> str:
        try:
            from prometheus_client import generate_latest  # type: ignore[import-untyped]
            return generate_latest().decode()
        except ImportError:
            return "# prometheus_client not installed\n"

    return router


__all__ = ["FastAPIHealthRouter", "FastAPIMetricsRouter", "ReadinessCheck"]
