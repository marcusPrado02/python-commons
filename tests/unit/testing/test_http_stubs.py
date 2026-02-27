"""Unit tests for §95 – HTTP Stubs."""
from __future__ import annotations

import asyncio

import pytest

from mp_commons.testing.http import HttpStubServer, StubCallCountError


class TestHttpStubServer:
    def test_stub_get_returns_json(self):
        async def run():
            import httpx
            with HttpStubServer() as stub:
                stub.stub_get("https://api.example.com/data", {"result": 42})
                async with httpx.AsyncClient() as client:
                    resp = await client.get("https://api.example.com/data")
                assert resp.status_code == 200
                assert resp.json() == {"result": 42}

        asyncio.run(run())

    def test_stub_get_custom_status(self):
        async def run():
            import httpx
            with HttpStubServer() as stub:
                stub.stub_get("https://api.example.com/miss", None, status=404)
                async with httpx.AsyncClient() as client:
                    resp = await client.get("https://api.example.com/miss")
                assert resp.status_code == 404

        asyncio.run(run())

    def test_stub_post_returns_json(self):
        async def run():
            import httpx
            with HttpStubServer() as stub:
                stub.stub_post("https://api.example.com/create", response_json={"id": 1})
                async with httpx.AsyncClient() as client:
                    resp = await client.post("https://api.example.com/create", json={"name": "x"})
                assert resp.status_code == 200
                assert resp.json() == {"id": 1}

        asyncio.run(run())

    def test_assert_called_exact_count(self):
        async def run():
            import httpx
            with HttpStubServer() as stub:
                stub.stub_get("https://api.example.com/ping", {"ok": True})
                async with httpx.AsyncClient() as client:
                    await client.get("https://api.example.com/ping")
                    await client.get("https://api.example.com/ping")
                stub.assert_called("https://api.example.com/ping", times=2)

        asyncio.run(run())

    def test_assert_called_wrong_count_raises(self):
        async def run():
            import httpx
            with HttpStubServer() as stub:
                stub.stub_get("https://api.example.com/once", {})
                async with httpx.AsyncClient() as client:
                    await client.get("https://api.example.com/once")
                stub.assert_called("https://api.example.com/once", times=2)

        with pytest.raises(StubCallCountError, match="1 time"):
            asyncio.run(run())

    def test_call_count_returns_zero_for_unstubbed(self):
        with HttpStubServer() as stub:
            assert stub.call_count("https://never-called.com") == 0

    def test_reset_clears_call_counts(self):
        async def run():
            import httpx
            with HttpStubServer() as stub:
                stub.stub_get("https://api.example.com/r", {})
                async with httpx.AsyncClient() as client:
                    await client.get("https://api.example.com/r")
                assert stub.call_count("https://api.example.com/r") == 1
                stub.reset()
                assert stub.call_count("https://api.example.com/r") == 0

        asyncio.run(run())

    def test_stub_post_with_response_fn(self):
        async def run():
            import httpx
            with HttpStubServer() as stub:
                stub.stub_post(
                    "https://api.example.com/echo",
                    response_fn=lambda req: httpx.Response(201, json={"echo": True}),
                )
                async with httpx.AsyncClient() as client:
                    resp = await client.post("https://api.example.com/echo", json={})
                assert resp.status_code == 201

        asyncio.run(run())
