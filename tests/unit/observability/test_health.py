"""Unit tests for §80 – Observability Health Checks."""
import asyncio

import pytest

from mp_commons.observability.health import (
    HealthCheck,
    HealthRegistry,
    HealthReport,
    HealthStatus,
    LambdaHealthCheck,
)


class _OkCheck(HealthCheck):
    @property
    def name(self) -> str:
        return "ok_check"

    async def check(self) -> HealthStatus:
        return HealthStatus(healthy=True, detail="all good")


class _FailCheck(HealthCheck):
    @property
    def name(self) -> str:
        return "fail_check"

    async def check(self) -> HealthStatus:
        return HealthStatus(healthy=False, detail="db unreachable")


class _BoomCheck(HealthCheck):
    @property
    def name(self) -> str:
        return "boom"

    async def check(self) -> HealthStatus:
        raise RuntimeError("unexpected crash")


class TestHealthRegistry:
    def test_all_healthy(self):
        reg = HealthRegistry()
        reg.register(_OkCheck())
        report = asyncio.run(reg.run_all())
        assert report.overall is True
        assert "ok_check" in report.results

    def test_one_failure_makes_overall_false(self):
        reg = HealthRegistry()
        reg.register(_OkCheck())
        reg.register(_FailCheck())
        report = asyncio.run(reg.run_all())
        assert report.overall is False

    def test_exception_captured_as_failure(self):
        reg = HealthRegistry()
        reg.register(_BoomCheck())
        report = asyncio.run(reg.run_all())
        assert report.overall is False
        assert "boom" in report.results
        assert "exception" in report.results["boom"].detail

    def test_latency_ms_positive(self):
        reg = HealthRegistry()
        reg.register(_OkCheck())
        report = asyncio.run(reg.run_all())
        assert report.results["ok_check"].latency_ms >= 0

    def test_to_dict(self):
        reg = HealthRegistry()
        reg.register(_OkCheck())
        report = asyncio.run(reg.run_all())
        d = report.to_dict()
        assert d["healthy"] is True
        assert "ok_check" in d["checks"]

    def test_empty_registry_is_healthy(self):
        reg = HealthRegistry()
        report = asyncio.run(reg.run_all())
        assert report.overall is True


class TestLambdaHealthCheck:
    def test_lambda_check_passes(self):
        async def fn():
            return HealthStatus(healthy=True)

        check = LambdaHealthCheck("custom", fn)
        status = asyncio.run(check.timed_check())
        assert status.healthy is True

    def test_lambda_check_fails(self):
        async def fn():
            return HealthStatus(healthy=False, detail="no conn")

        check = LambdaHealthCheck("db", fn)
        status = asyncio.run(check.timed_check())
        assert status.healthy is False
        assert status.detail == "no conn"
