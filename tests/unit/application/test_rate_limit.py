"""Unit tests for rate limiting — §12."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from mp_commons.application.rate_limit import (
    LocalTokenBucketRateLimiter,
    Quota,
    RateLimitDecision,
    RateLimitResult,
    RateLimiter,
)


# ---------------------------------------------------------------------------
# Quota (12.1)
# ---------------------------------------------------------------------------


class TestQuota:
    def test_window_label(self) -> None:
        q = Quota(key="api", limit=100, window_seconds=60)
        assert q.window_label == "100 req/60s"

    def test_frozen(self) -> None:
        q = Quota(key="q", limit=10, window_seconds=1)
        with pytest.raises((AttributeError, TypeError)):
            q.limit = 20  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RateLimitResult (12.1)
# ---------------------------------------------------------------------------


class TestRateLimitResult:
    def _result(self, decision: RateLimitDecision, remaining: int = 5) -> RateLimitResult:
        return RateLimitResult(
            decision=decision,
            remaining=remaining,
            reset_at=datetime.now(UTC) + timedelta(seconds=60),
            quota=Quota(key="k", limit=10, window_seconds=60),
        )

    def test_allowed_property(self) -> None:
        assert self._result(RateLimitDecision.ALLOWED).allowed is True
        assert self._result(RateLimitDecision.DENIED).allowed is False

    def test_retry_after_positive_when_denied(self) -> None:
        result = self._result(RateLimitDecision.DENIED, remaining=0)
        assert result.retry_after_seconds > 0


# ---------------------------------------------------------------------------
# LocalTokenBucketRateLimiter (12.2)
# ---------------------------------------------------------------------------


class TestLocalTokenBucketRateLimiter:
    def _quota(self, limit: int = 3, window: int = 60) -> Quota:
        return Quota(key="test", limit=limit, window_seconds=window)

    def test_allowed_within_limit(self) -> None:
        limiter = LocalTokenBucketRateLimiter()
        quota = self._quota(limit=3)

        results = [asyncio.run(limiter.check(quota, "user-1")) for _ in range(3)]
        assert all(r.allowed for r in results)

    def test_denied_over_limit(self) -> None:
        limiter = LocalTokenBucketRateLimiter()
        quota = self._quota(limit=2)

        asyncio.run(limiter.check(quota, "user-1"))
        asyncio.run(limiter.check(quota, "user-1"))
        result = asyncio.run(limiter.check(quota, "user-1"))
        assert result.allowed is False
        assert result.decision == RateLimitDecision.DENIED

    def test_remaining_decrements(self) -> None:
        limiter = LocalTokenBucketRateLimiter()
        quota = self._quota(limit=5)

        r1 = asyncio.run(limiter.check(quota, "u"))
        r2 = asyncio.run(limiter.check(quota, "u"))
        assert r1.remaining == 4
        assert r2.remaining == 3

    def test_reset_clears_bucket(self) -> None:
        limiter = LocalTokenBucketRateLimiter()
        quota = self._quota(limit=1)

        asyncio.run(limiter.check(quota, "user-1"))
        denied = asyncio.run(limiter.check(quota, "user-1"))
        assert denied.allowed is False

        asyncio.run(limiter.reset(quota, "user-1"))
        allowed = asyncio.run(limiter.check(quota, "user-1"))
        assert allowed.allowed is True

    def test_different_identifiers_independent(self) -> None:
        limiter = LocalTokenBucketRateLimiter()
        quota = self._quota(limit=1)

        asyncio.run(limiter.check(quota, "user-1"))
        # user-2's bucket is separate
        r = asyncio.run(limiter.check(quota, "user-2"))
        assert r.allowed is True

    def test_reset_nonexistent_is_noop(self) -> None:
        limiter = LocalTokenBucketRateLimiter()
        quota = self._quota()
        asyncio.run(limiter.reset(quota, "ghost"))  # must not raise


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.application.rate_limit")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"
