"""Unit tests for §96 Load Testing — LoadReport and LoadTestRunner."""
import asyncio
import time

import pytest

from mp_commons.testing.load import LoadReport, LoadTestError, LoadTestRunner


# ---------------------------------------------------------------------------
# LoadReport percentile & assertion tests
# ---------------------------------------------------------------------------

def _make_report(latencies, failures=0, duration=1.0):
    return LoadReport(
        total_requests=len(latencies) + failures,
        failures=failures,
        latencies_ms=latencies,
        duration_sec=duration,
    )


def test_loadreport_percentiles_empty():
    r = _make_report([])
    assert r.p50_ms == 0.0
    assert r.p95_ms == 0.0
    assert r.p99_ms == 0.0
    assert r.max_ms == 0.0
    assert r.min_ms == 0.0
    assert r.mean_ms == 0.0


def test_loadreport_percentiles_single():
    r = _make_report([42.0])
    assert r.p50_ms == 42.0
    assert r.p95_ms == 42.0
    assert r.p99_ms == 42.0
    assert r.max_ms == 42.0
    assert r.min_ms == 42.0
    assert r.mean_ms == 42.0


def test_loadreport_percentiles_multiple():
    # 100 values: 1..100 ms
    latencies = [float(i) for i in range(1, 101)]
    r = _make_report(latencies)
    assert r.p50_ms == 50.0
    assert r.p95_ms == 95.0
    assert r.p99_ms == 99.0
    assert r.max_ms == 100.0
    assert r.min_ms == 1.0
    assert abs(r.mean_ms - 50.5) < 0.01


def test_loadreport_rps():
    r = _make_report([1.0] * 100, duration=10.0)
    assert r.rps == pytest.approx(10.0)


def test_loadreport_error_rate_zero():
    r = _make_report([1.0, 2.0, 3.0], failures=0)
    assert r.error_rate == 0.0


def test_loadreport_error_rate_nonzero():
    r = _make_report([1.0, 2.0], failures=2)
    # 4 total, 2 failures
    assert r.error_rate == pytest.approx(0.5)


def test_loadreport_success_count():
    r = _make_report([1.0, 2.0], failures=3)
    assert r.success_count == 2


def test_loadreport_assert_p99_below_passes():
    r = _make_report([float(i) for i in range(1, 101)])
    r.assert_p99_below(100.0)  # p99 == 99.0, should not raise


def test_loadreport_assert_p99_below_raises():
    r = _make_report([float(i) for i in range(1, 101)])
    with pytest.raises(LoadTestError, match="p99"):
        r.assert_p99_below(50.0)  # p99 == 99.0 > 50.0


def test_loadreport_assert_error_rate_below_passes():
    r = _make_report([1.0, 2.0], failures=0)
    r.assert_error_rate_below(0.1)


def test_loadreport_assert_error_rate_below_raises():
    r = _make_report([1.0, 2.0], failures=2)
    with pytest.raises(LoadTestError, match="error rate"):
        r.assert_error_rate_below(0.1)


def test_loadreport_assert_rps_above_passes():
    r = _make_report([1.0] * 50, duration=5.0)
    r.assert_rps_above(5.0)  # rps == 10.0


def test_loadreport_assert_rps_above_raises():
    r = _make_report([1.0] * 5, duration=10.0)
    with pytest.raises(LoadTestError, match="rps"):
        r.assert_rps_above(10.0)  # rps == 0.5


def test_loadreport_summary_keys():
    r = _make_report([10.0, 20.0, 30.0])
    s = r.summary()
    for key in ("total_requests", "failures", "error_rate", "rps",
                "p50_ms", "p95_ms", "p99_ms", "max_ms", "min_ms", "mean_ms"):
        assert key in s, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# LoadTestRunner tests
# ---------------------------------------------------------------------------

def test_load_runner_collects_latencies():
    call_count = 0

    async def scenario():
        nonlocal call_count
        call_count += 1

    runner = LoadTestRunner()
    report = asyncio.run(runner.run(scenario, users=3, duration_sec=0.3))

    assert report.total_requests >= 3
    assert report.failures == 0
    assert len(report.latencies_ms) == report.success_count


def test_load_runner_captures_failures():
    async def bad_scenario():
        raise ValueError("intentional")

    runner = LoadTestRunner()
    report = asyncio.run(runner.run(bad_scenario, users=2, duration_sec=0.3))

    assert report.failures > 0
    assert report.error_rate > 0.0


def test_load_runner_mixed_scenario():
    call_count = 0

    async def mixed():
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:
            raise RuntimeError("every second call fails")

    runner = LoadTestRunner()
    report = asyncio.run(runner.run(mixed, users=1, duration_sec=0.3))

    assert report.total_requests >= 2
    assert report.failures >= 1
    assert report.success_count >= 1


def test_load_runner_report_duration_reasonable():
    async def fast():
        pass

    runner = LoadTestRunner()
    report = asyncio.run(runner.run(fast, users=2, duration_sec=0.2, ramp_up_sec=0.0))

    assert report.duration_sec >= 0.15  # allow some scheduling slack
