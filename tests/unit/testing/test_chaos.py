"""Unit tests for testing chaos injectors (§39)."""

from __future__ import annotations

import asyncio
import time

import pytest

from mp_commons.testing.chaos import FailureInjector, LatencyInjector, ToxiproxyHarness


# ---------------------------------------------------------------------------
# §39.1  LatencyInjector
# ---------------------------------------------------------------------------


class TestLatencyInjector:
    def test_default_range(self) -> None:
        inj = LatencyInjector(min_ms=0.1, max_ms=1.0)
        assert inj._min < inj._max

    def test_call_awaitable_returns_result(self) -> None:
        inj = LatencyInjector(min_ms=0.0, max_ms=1.0)

        async def coro() -> str:
            return "ok"

        result = asyncio.run(inj.call(coro()))
        assert result == "ok"

    def test_call_adds_delay(self) -> None:
        inj = LatencyInjector(min_ms=50.0, max_ms=51.0)

        async def coro() -> int:
            return 42

        start = time.monotonic()
        asyncio.run(inj.call(coro()))
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms >= 40  # generous lower bound

    def test_call_non_awaitable_returns_value(self) -> None:
        inj = LatencyInjector(min_ms=0.0, max_ms=1.0)
        result = asyncio.run(inj.call(99))
        assert result == 99

    def test_call_preserves_result_type(self) -> None:
        inj = LatencyInjector(min_ms=0.0, max_ms=1.0)

        async def coro() -> dict:
            return {"key": "value"}

        result = asyncio.run(inj.call(coro()))
        assert result == {"key": "value"}


# ---------------------------------------------------------------------------
# §39.2  FailureInjector
# ---------------------------------------------------------------------------


class TestFailureInjector:
    def test_zero_rate_never_fails(self) -> None:
        inj = FailureInjector(failure_rate=0.0)

        async def coro() -> str:
            return "success"

        for _ in range(20):
            result = asyncio.run(inj.call(coro()))
            assert result == "success"

    def test_full_rate_always_fails(self) -> None:
        inj = FailureInjector(failure_rate=1.0)

        async def coro() -> str:
            return "never"

        for _ in range(5):
            with pytest.raises(Exception):
                asyncio.run(inj.call(coro()))

    def test_raises_default_exception_type(self) -> None:
        from mp_commons.kernel.errors import ExternalServiceError

        inj = FailureInjector(failure_rate=1.0)

        async def coro() -> None:
            pass

        with pytest.raises(ExternalServiceError):
            asyncio.run(inj.call(coro()))

    def test_custom_exception_factory(self) -> None:
        inj = FailureInjector(
            failure_rate=1.0,
            exception_factory=lambda: ValueError("custom"),
        )

        async def coro() -> None:
            pass

        with pytest.raises(ValueError, match="custom"):
            asyncio.run(inj.call(coro()))

    def test_invalid_failure_rate_raises(self) -> None:
        with pytest.raises(ValueError):
            FailureInjector(failure_rate=1.5)

        with pytest.raises(ValueError):
            FailureInjector(failure_rate=-0.1)

    def test_probabilistic_failures_within_bounds(self) -> None:
        """At rate=0.5, expect roughly 40-60% failures over 200 trials."""
        inj = FailureInjector(failure_rate=0.5)
        failures = 0

        async def coro() -> None:
            pass

        async def run_once() -> None:
            nonlocal failures
            try:
                await inj.call(coro())
            except Exception:
                failures += 1

        async def run_all() -> None:
            for _ in range(200):
                await run_once()

        asyncio.run(run_all())
        # Wide tolerance: expect 50% ± 20%
        assert 60 <= failures <= 140

    def test_non_awaitable_coro_with_zero_rate(self) -> None:
        inj = FailureInjector(failure_rate=0.0)
        result = asyncio.run(inj.call(42))
        assert result == 42


# ---------------------------------------------------------------------------
# §39.3  ToxiproxyHarness (API surface — no real network calls)
# ---------------------------------------------------------------------------


class TestToxiproxyHarness:
    def test_default_api_url(self) -> None:
        harness = ToxiproxyHarness()
        assert "8474" in harness._api

    def test_custom_api_url(self) -> None:
        harness = ToxiproxyHarness(api_url="http://toxiproxy:8474")
        assert harness._api == "http://toxiproxy:8474"

    def test_trailing_slash_stripped(self) -> None:
        harness = ToxiproxyHarness(api_url="http://localhost:8474/")
        assert not harness._api.endswith("/")

    def test_latency_is_async_context_manager(self) -> None:
        harness = ToxiproxyHarness()
        cm = harness.latency("my-proxy")
        assert hasattr(cm, "__aenter__") and hasattr(cm, "__aexit__")

    def test_bandwidth_is_async_context_manager(self) -> None:
        harness = ToxiproxyHarness()
        cm = harness.bandwidth("my-proxy")
        assert hasattr(cm, "__aenter__") and hasattr(cm, "__aexit__")

    def test_timeout_is_async_context_manager(self) -> None:
        harness = ToxiproxyHarness()
        cm = harness.timeout("my-proxy")
        assert hasattr(cm, "__aenter__") and hasattr(cm, "__aexit__")
