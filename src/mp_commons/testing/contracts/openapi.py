"""OpenAPI contract test base class."""

from __future__ import annotations

from typing import Any

__all__ = ["OpenAPIContractTest"]


class OpenAPIContractTest:
    """Base class for OpenAPI contract tests.

    Subclass and override ``openapi_url`` to test your service's spec.

    Example::

        class TestOrderAPI(OpenAPIContractTest):
            openapi_url = "http://localhost:8000/openapi.json"

        @pytest.mark.contract
        async def test_schema(self, contract_test):
            await contract_test.assert_valid_schema()
    """

    openapi_url: str = ""

    async def load_spec(self) -> dict[str, Any]:
        import httpx  # type: ignore[import-untyped]

        async with httpx.AsyncClient() as client:
            resp = await client.get(self.openapi_url)
            resp.raise_for_status()
            return resp.json()

    async def assert_valid_schema(self) -> None:
        spec = await self.load_spec()
        assert "openapi" in spec, "Not a valid OpenAPI document"
        assert "paths" in spec, "OpenAPI document has no paths"
