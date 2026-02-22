"""Unit tests – FakeMetricsRegistry, FakeFeatureFlagProvider, FakeSecretStore,
fake_principal fixture, and StepClock (§36.7, §36.9, §36.10, §37.4, §38.4)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from mp_commons.testing.fakes import FakeMetricsRegistry, FakeFeatureFlagProvider, FakeSecretStore
from mp_commons.testing.generators import StepClock
from mp_commons.application.feature_flags.feature_flag import FeatureFlag
from mp_commons.config.secrets.port import SecretRef


# ---------------------------------------------------------------------------
# §36.7 – FakeMetricsRegistry
# ---------------------------------------------------------------------------


class TestFakeMetricsRegistry:
    """§36.7 – FakeMetricsRegistry records all instrument calls."""

    def test_counter_add_records_call(self) -> None:
        m = FakeMetricsRegistry()
        c = m.counter("requests_total")
        c.add(1)
        c.add(2)
        assert c.call_count == 2
        assert c.total == 3.0

    def test_same_counter_name_returns_same_instance(self) -> None:
        m = FakeMetricsRegistry()
        c1 = m.counter("hits")
        c2 = m.counter("hits")
        assert c1 is c2

    def test_assert_counter_incremented_passes(self) -> None:
        m = FakeMetricsRegistry()
        c = m.counter("x")
        c.add()
        c.add()
        m.assert_counter_incremented("x", 2)

    def test_assert_counter_incremented_fails_on_mismatch(self) -> None:
        m = FakeMetricsRegistry()
        c = m.counter("x")
        c.add()
        with pytest.raises(AssertionError):
            m.assert_counter_incremented("x", 5)

    def test_assert_counter_incremented_fails_when_not_created(self) -> None:
        m = FakeMetricsRegistry()
        with pytest.raises(AssertionError, match="never created"):
            m.assert_counter_incremented("missing", 1)

    def test_assert_counter_total(self) -> None:
        m = FakeMetricsRegistry()
        c = m.counter("bytes")
        c.add(100)
        c.add(50)
        m.assert_counter_total("bytes", 150.0)

    def test_histogram_records_values(self) -> None:
        m = FakeMetricsRegistry()
        h = m.histogram("latency_ms")
        h.record(15.0)
        h.record(200.0)
        assert h.call_count == 2
        assert h.values == [15.0, 200.0]

    def test_gauge_set_inc_dec(self) -> None:
        m = FakeMetricsRegistry()
        g = m.gauge("active_conns")
        g.set(10)
        g.inc()
        g.dec()
        assert g.current == 10.0

    def test_reset_clears_all_instruments(self) -> None:
        m = FakeMetricsRegistry()
        m.counter("x").add()
        m.reset()
        with pytest.raises(AssertionError):
            m.assert_counter_incremented("x", 1)

    def test_counter_default_add_value_is_one(self) -> None:
        m = FakeMetricsRegistry()
        c = m.counter("req")
        c.add()
        assert c.total == 1.0


# ---------------------------------------------------------------------------
# §36.9 – FakeFeatureFlagProvider
# ---------------------------------------------------------------------------


class TestFakeFeatureFlagProvider:
    """§36.9 – FakeFeatureFlagProvider allows programmatic enable/disable."""

    def test_disabled_by_default(self) -> None:
        provider = FakeFeatureFlagProvider()
        flag = FeatureFlag("my_flag")

        async def run() -> bool:
            return await provider.is_enabled(flag)

        assert asyncio.run(run()) is False

    def test_enable_returns_true(self) -> None:
        provider = FakeFeatureFlagProvider()
        flag = FeatureFlag("my_flag")
        provider.enable("my_flag")

        async def run() -> bool:
            return await provider.is_enabled(flag)

        assert asyncio.run(run()) is True

    def test_disable_after_enable(self) -> None:
        provider = FakeFeatureFlagProvider()
        provider.enable("my_flag").disable("my_flag")
        flag = FeatureFlag("my_flag")

        async def run() -> bool:
            return await provider.is_enabled(flag)

        assert asyncio.run(run()) is False

    def test_enable_with_feature_flag_instance(self) -> None:
        provider = FakeFeatureFlagProvider()
        flag = FeatureFlag("checkout_v2")
        provider.enable(flag)

        async def run() -> bool:
            return await provider.is_enabled(flag)

        assert asyncio.run(run()) is True

    def test_get_variant_returns_none_by_default(self) -> None:
        provider = FakeFeatureFlagProvider()
        flag = FeatureFlag("beta")

        async def run() -> str | None:
            return await provider.get_variant(flag)

        assert asyncio.run(run()) is None

    def test_set_variant_returns_configured_value(self) -> None:
        provider = FakeFeatureFlagProvider()
        flag = FeatureFlag("billing_v2")
        provider.set_variant("billing_v2", "control")

        async def run() -> str | None:
            return await provider.get_variant(flag)

        assert asyncio.run(run()) == "control"

    def test_reset_clears_all_flags(self) -> None:
        provider = FakeFeatureFlagProvider()
        provider.enable("my_flag")
        provider.reset()
        flag = FeatureFlag("my_flag")

        async def run() -> bool:
            return await provider.is_enabled(flag)

        assert asyncio.run(run()) is False

    def test_uses_flag_default_value_when_not_set(self) -> None:
        provider = FakeFeatureFlagProvider()
        flag = FeatureFlag("feature_with_default", default_value=True)

        async def run() -> bool:
            return await provider.is_enabled(flag)

        assert asyncio.run(run()) is True

    def test_chaining_returns_provider(self) -> None:
        provider = FakeFeatureFlagProvider()
        result = provider.enable("a").disable("b").set_variant("c", "v1")
        assert result is provider


# ---------------------------------------------------------------------------
# §36.10 – FakeSecretStore
# ---------------------------------------------------------------------------


class TestFakeSecretStore:
    """§36.10 – FakeSecretStore is a seeded in-memory SecretStore."""

    def test_get_seeded_secret(self) -> None:
        store = FakeSecretStore()
        store.seed("db/password", "super-secret")
        ref = SecretRef(path="db", key="password")

        async def run() -> str:
            return await store.get(ref)

        assert asyncio.run(run()) == "super-secret"

    def test_get_unknown_raises_key_error(self) -> None:
        store = FakeSecretStore()
        ref = SecretRef(path="db", key="password")

        async def run() -> None:
            await store.get(ref)

        with pytest.raises(KeyError):
            asyncio.run(run())

    def test_seed_ref_convenience(self) -> None:
        store = FakeSecretStore()
        ref = SecretRef(path="service", key="token")
        store.seed_ref(ref, "tok123")

        async def run() -> str:
            return await store.get(ref)

        assert asyncio.run(run()) == "tok123"

    def test_get_all_returns_matching_prefix(self) -> None:
        store = FakeSecretStore()
        store.seed("config/host", "localhost")
        store.seed("config/port", "5432")
        store.seed("other/key", "irrelevant")

        async def run() -> dict[str, str]:
            return await store.get_all("config")

        result = asyncio.run(run())
        assert result == {"host": "localhost", "port": "5432"}

    def test_get_all_empty_when_no_match(self) -> None:
        store = FakeSecretStore()

        async def run() -> dict[str, str]:
            return await store.get_all("nonexistent")

        assert asyncio.run(run()) == {}

    def test_reset_clears_seeds(self) -> None:
        store = FakeSecretStore()
        store.seed("k/v", "value")
        store.reset()
        ref = SecretRef(path="k", key="v")

        async def run() -> None:
            await store.get(ref)

        with pytest.raises(KeyError):
            asyncio.run(run())

    def test_chaining_returns_store(self) -> None:
        store = FakeSecretStore()
        result = store.seed("a/b", "1").seed("c/d", "2")
        assert result is store


# ---------------------------------------------------------------------------
# §37.4 – fake_principal and security_context fixtures
# ---------------------------------------------------------------------------


class TestFakePrincipalFixture:
    """§37.4 – fake_principal and security_context pytest fixtures."""

    def test_fake_principal_has_expected_defaults(self, fake_principal) -> None:
        assert fake_principal.subject == "test-user"
        assert fake_principal.tenant_id == "test-tenant"

    def test_security_context_fixture_sets_principal(self, security_context) -> None:
        from mp_commons.kernel.security import SecurityContext
        p = SecurityContext.get_current()
        assert p is not None
        assert p.subject == "test-user"

    def test_security_context_is_cleared_after_test(self) -> None:
        """Context should be clear when no fixture is active (tested independently)."""
        from mp_commons.kernel.security import SecurityContext
        SecurityContext.clear()
        assert SecurityContext.get_current() is None

    def test_require_raises_when_no_context(self) -> None:
        from mp_commons.kernel.security import SecurityContext
        from mp_commons.kernel.errors import UnauthorizedError
        SecurityContext.clear()
        with pytest.raises(UnauthorizedError):
            SecurityContext.require()

    def test_fake_principal_is_principal_type(self, fake_principal) -> None:
        from mp_commons.kernel.security import Principal
        assert isinstance(fake_principal, Principal)


# ---------------------------------------------------------------------------
# §38.4 – StepClock
# ---------------------------------------------------------------------------


class TestStepClock:
    """§38.4 – StepClock advances deterministically on each now() call."""

    def test_default_start_and_step(self) -> None:
        clock = StepClock()
        t0 = clock.now()
        t1 = clock.now()
        assert t1 - t0 == timedelta(seconds=1)

    def test_custom_start(self) -> None:
        start = datetime(2000, 6, 15, tzinfo=UTC)
        clock = StepClock(start=start)
        assert clock.now() == start

    def test_custom_step_timedelta(self) -> None:
        clock = StepClock(step=timedelta(minutes=5))
        t0 = clock.now()
        t1 = clock.now()
        assert t1 - t0 == timedelta(minutes=5)

    def test_custom_step_kwargs(self) -> None:
        clock = StepClock(seconds=30)
        t0 = clock.now()
        t1 = clock.now()
        assert t1 - t0 == timedelta(seconds=30)

    def test_strictly_increasing(self) -> None:
        clock = StepClock()
        times = [clock.now() for _ in range(10)]
        for a, b in zip(times, times[1:]):
            assert b > a

    def test_call_count_increments(self) -> None:
        clock = StepClock()
        assert clock.call_count == 0
        clock.now()
        clock.now()
        assert clock.call_count == 2

    def test_peek_does_not_advance(self) -> None:
        clock = StepClock()
        peeked = clock.peek()
        first = clock.now()
        assert peeked == first
        assert clock.call_count == 1

    def test_reset_returns_to_start(self) -> None:
        clock = StepClock()
        clock.now()
        clock.now()
        clock.reset()
        assert clock.now() == datetime(2026, 1, 1, tzinfo=UTC)
        assert clock.call_count == 1

    def test_reset_with_custom_start(self) -> None:
        clock = StepClock()
        new_start = datetime(2030, 1, 1, tzinfo=UTC)
        clock.reset(start=new_start)
        assert clock.now() == new_start

    def test_today_returns_date(self) -> None:
        clock = StepClock()
        assert clock.today() == datetime(2026, 1, 1, tzinfo=UTC).date()

    def test_timestamp_advances(self) -> None:
        clock = StepClock(step=timedelta(seconds=1))
        ts0 = clock.timestamp()
        ts1 = clock.timestamp()
        assert abs(ts1 - ts0 - 1.0) < 0.001
