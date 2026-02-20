"""FastAPI adapter – FastAPIHealthRouter, FastAPIMetricsRouter."""
from __future__ import annotations

from typing import Any


def _require_fastapi() -> None:
    try:
        import fastapi  # noqa: F401
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[fastapi]' to use the FastAPI adapter") from exc


def FastAPIHealthRouter(path: str = "/health") -> Any:
    """Return a minimal liveness/readiness router."""
    _require_fastapi()
    from fastapi import APIRouter  # type: ignore[import-untyped]

    router = APIRouter()

    @router.get(path, tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get(f"{path}/live", tags=["ops"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @router.get(f"{path}/ready", tags=["ops"])
    async def readiness() -> dict[str, str]:
        return {"status": "ok"}

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
            return "# prometheus_client not installed
"

    return router


__all__ = ["FastAPIHealthRouter", "FastAPIMetricsRouter"]
