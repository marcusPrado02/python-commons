"""Testing chaos – ToxiproxyHarness."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator


class _ToxicContext:
    def __init__(self, harness: "ToxiproxyHarness", proxy_name: str, toxic_name: str) -> None:
        self._harness = harness
        self._proxy = proxy_name
        self._name = toxic_name

    async def __aenter__(self) -> "_ToxicContext":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._harness._delete_toxic(self._proxy, self._name)


class ToxiproxyHarness:
    """Control a Toxiproxy instance via its HTTP API."""

    def __init__(self, api_url: str = "http://localhost:8474") -> None:
        self._api = api_url.rstrip("/")

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            import httpx  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError("Install httpx to use ToxiproxyHarness") from exc
        async with httpx.AsyncClient() as client:
            resp = await client.request(method, f"{self._api}{path}", **kwargs)
            resp.raise_for_status()
            return resp.json() if resp.content else {}

    async def _delete_toxic(self, proxy_name: str, toxic_name: str) -> None:
        await self._request("DELETE", f"/proxies/{proxy_name}/toxics/{toxic_name}")

    @asynccontextmanager
    async def latency(
        self, proxy_name: str, latency_ms: int = 1000, jitter_ms: int = 0, toxic_name: str = "latency"
    ) -> AsyncIterator[_ToxicContext]:
        await self._request(
            "POST",
            f"/proxies/{proxy_name}/toxics",
            json={"name": toxic_name, "type": "latency", "attributes": {"latency": latency_ms, "jitter": jitter_ms}},
        )
        ctx = _ToxicContext(self, proxy_name, toxic_name)
        try:
            yield ctx
        finally:
            await self._delete_toxic(proxy_name, toxic_name)

    @asynccontextmanager
    async def bandwidth(
        self, proxy_name: str, rate_kb: int = 100, toxic_name: str = "bandwidth"
    ) -> AsyncIterator[_ToxicContext]:
        await self._request(
            "POST",
            f"/proxies/{proxy_name}/toxics",
            json={"name": toxic_name, "type": "bandwidth", "attributes": {"rate": rate_kb}},
        )
        ctx = _ToxicContext(self, proxy_name, toxic_name)
        try:
            yield ctx
        finally:
            await self._delete_toxic(proxy_name, toxic_name)

    @asynccontextmanager
    async def timeout(
        self, proxy_name: str, timeout_ms: int = 5000, toxic_name: str = "timeout"
    ) -> AsyncIterator[_ToxicContext]:
        await self._request(
            "POST",
            f"/proxies/{proxy_name}/toxics",
            json={"name": toxic_name, "type": "timeout", "attributes": {"timeout": timeout_ms}},
        )
        ctx = _ToxicContext(self, proxy_name, toxic_name)
        try:
            yield ctx
        finally:
            await self._delete_toxic(proxy_name, toxic_name)


__all__ = ["ToxiproxyHarness"]
