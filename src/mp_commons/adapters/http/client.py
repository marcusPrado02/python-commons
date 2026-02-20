"""HTTP adapter – HttpxHttpClient."""
from __future__ import annotations

from typing import Any

from mp_commons.kernel.errors import ExternalServiceError, TimeoutError as AppTimeoutError


def _require_httpx() -> Any:
    try:
        import httpx  # type: ignore[import-untyped]
        return httpx
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[httpx]' to use the HTTPX adapter") from exc


class HttpxHttpClient:
    """Thin async httpx wrapper with structured error mapping."""

    def __init__(self, base_url: str = "", timeout: float = 10.0, **kwargs: Any) -> None:
        httpx = _require_httpx()
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, **kwargs)

    async def __aenter__(self) -> "HttpxHttpClient":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.__aexit__(*args)

    async def get(self, url: str, **kwargs: Any) -> Any:
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Any:
        return await self._request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> Any:
        return await self._request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> Any:
        return await self._request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Any:
        return await self._request("DELETE", url, **kwargs)

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        httpx = _require_httpx()
        try:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise AppTimeoutError(f"HTTP request timed out: {method} {url}") from exc
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(
                service=url,
                message=f"HTTP {exc.response.status_code} from {method} {url}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise ExternalServiceError(service=url, message=str(exc)) from exc


HttpClient = HttpxHttpClient

__all__ = ["HttpClient", "HttpxHttpClient"]
