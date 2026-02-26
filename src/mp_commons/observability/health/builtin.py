from __future__ import annotations

from mp_commons.observability.health.check import HealthCheck, HealthStatus

__all__ = [
    "DatabaseHealthCheck",
    "HttpEndpointHealthCheck",
    "LambdaHealthCheck",
    "RedisHealthCheck",
]


class LambdaHealthCheck(HealthCheck):
    """Simple health check backed by a callable — useful in tests."""

    def __init__(self, name_: str, fn) -> None:
        self._name = name_
        self._fn = fn

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> HealthStatus:
        return await self._fn()


class DatabaseHealthCheck(HealthCheck):
    """Checks DB connectivity by running a lightweight query."""

    def __init__(self, session_factory) -> None:
        self._factory = session_factory

    @property
    def name(self) -> str:
        return "database"

    async def check(self) -> HealthStatus:
        try:
            async with self._factory() as session:
                await session.execute(__import__("sqlalchemy").text("SELECT 1"))
            return HealthStatus(healthy=True)
        except Exception as exc:  # noqa: BLE001
            return HealthStatus(healthy=False, detail=str(exc))


class RedisHealthCheck(HealthCheck):
    """Checks Redis connectivity with a PING."""

    def __init__(self, cache) -> None:
        self._cache = cache

    @property
    def name(self) -> str:
        return "redis"

    async def check(self) -> HealthStatus:
        try:
            await self._cache.ping()
            return HealthStatus(healthy=True)
        except Exception as exc:  # noqa: BLE001
            return HealthStatus(healthy=False, detail=str(exc))


class HttpEndpointHealthCheck(HealthCheck):
    """Checks an HTTP endpoint by making a GET request."""

    def __init__(self, url: str, expected_status: int = 200, timeout: float = 5.0) -> None:
        self._url = url
        self._expected = expected_status
        self._timeout = timeout
        self._name = f"http:{url}"

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> HealthStatus:
        try:
            import httpx  # optional
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(self._url)
            if resp.status_code == self._expected:
                return HealthStatus(healthy=True)
            return HealthStatus(healthy=False, detail=f"status={resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            return HealthStatus(healthy=False, detail=str(exc))
