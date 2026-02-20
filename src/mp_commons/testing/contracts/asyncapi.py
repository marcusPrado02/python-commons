"""AsyncAPI contract test base class."""

from __future__ import annotations

from typing import Any

__all__ = ["AsyncAPIContractTest"]


class AsyncAPIContractTest:
    """Base class for AsyncAPI contract tests."""

    asyncapi_url: str = ""

    async def load_spec(self) -> dict[str, Any]:
        import httpx  # type: ignore[import-untyped]

        async with httpx.AsyncClient() as client:
            resp = await client.get(self.asyncapi_url)
            resp.raise_for_status()
            return resp.json()

    async def assert_valid_schema(self) -> None:
        spec = await self.load_spec()
        assert "asyncapi" in spec, "Not a valid AsyncAPI document"
        assert "channels" in spec, "AsyncAPI document has no channels"
