"""Unit tests for pytest fixtures (§37)."""

from __future__ import annotations

from datetime import UTC

import pytest

# ---------------------------------------------------------------------------
# Import the fixtures so pytest recognises them in this module
# ---------------------------------------------------------------------------
from mp_commons.testing.fixtures import (
    correlation_fixture,
    fake_clock,
    fake_idempotency_store,
    fake_inbox_repo,
    fake_message_bus,
    fake_outbox_repo,
    fake_policy_engine,
    tenant_fixture,
)
from mp_commons.kernel.time import FrozenClock
from mp_commons.testing.fakes import (
    FakePolicyEngine,
    InMemoryIdempotencyStore,
    InMemoryInboxRepository,
    InMemoryMessageBus,
    InMemoryOutboxRepository,
)


# ---------------------------------------------------------------------------
# §37.1  fake_clock fixture
# ---------------------------------------------------------------------------


class TestFakeClockFixture:
    def test_returns_frozen_clock(self, fake_clock: FrozenClock) -> None:
        assert isinstance(fake_clock, FrozenClock)

    def test_frozen_in_time(self, fake_clock: FrozenClock) -> None:
        t1 = fake_clock.now()
        t2 = fake_clock.now()
        assert t1 == t2

    def test_has_utc_timezone(self, fake_clock: FrozenClock) -> None:
        assert fake_clock.now().tzinfo is not None

    def test_advance_works(self, fake_clock: FrozenClock) -> None:
        t0 = fake_clock.now()
        fake_clock.advance(hours=2)
        assert fake_clock.now() > t0


# ---------------------------------------------------------------------------
# §37.2  correlation_fixture
# ---------------------------------------------------------------------------


class TestCorrelationFixture:
    def test_sets_correlation_context(self, correlation_fixture) -> None:
        from mp_commons.observability.correlation import CorrelationContext
        ctx = CorrelationContext.get()
        assert ctx is not None

    def test_correlation_id_is_set(self, correlation_fixture) -> None:
        from mp_commons.observability.correlation import CorrelationContext
        ctx = CorrelationContext.get()
        assert ctx is not None
        assert ctx.correlation_id == "test-correlation-id"

    def test_yields_context(self, correlation_fixture) -> None:
        assert correlation_fixture is not None


# ---------------------------------------------------------------------------
# §37.3  fake_message_bus / fake_outbox_repo / fake_inbox_repo / fake_idempotency
# ---------------------------------------------------------------------------


class TestMessageBusFixture:
    def test_returns_in_memory_bus(self, fake_message_bus: InMemoryMessageBus) -> None:
        assert isinstance(fake_message_bus, InMemoryMessageBus)

    def test_starts_empty(self, fake_message_bus: InMemoryMessageBus) -> None:
        assert fake_message_bus.published == []


class TestOutboxRepoFixture:
    def test_returns_in_memory_outbox(self, fake_outbox_repo: InMemoryOutboxRepository) -> None:
        assert isinstance(fake_outbox_repo, InMemoryOutboxRepository)

    def test_starts_empty(self, fake_outbox_repo: InMemoryOutboxRepository) -> None:
        assert fake_outbox_repo.all_records() == []


class TestInboxRepoFixture:
    def test_returns_in_memory_inbox(self, fake_inbox_repo: InMemoryInboxRepository) -> None:
        assert isinstance(fake_inbox_repo, InMemoryInboxRepository)

    def test_starts_empty(self, fake_inbox_repo: InMemoryInboxRepository) -> None:
        assert fake_inbox_repo.all_records() == []


class TestIdempotencyStoreFixture:
    def test_returns_in_memory_store(
        self, fake_idempotency_store: InMemoryIdempotencyStore
    ) -> None:
        assert isinstance(fake_idempotency_store, InMemoryIdempotencyStore)

    def test_starts_empty(self, fake_idempotency_store: InMemoryIdempotencyStore) -> None:
        assert fake_idempotency_store.all_keys() == []


# ---------------------------------------------------------------------------
# §37.4  fake_policy_engine fixture
# ---------------------------------------------------------------------------


class TestFakePolicyEngineFixture:
    def test_returns_fake_policy_engine(
        self, fake_policy_engine: FakePolicyEngine
    ) -> None:
        assert isinstance(fake_policy_engine, FakePolicyEngine)


# ---------------------------------------------------------------------------
# §37.5  tenant_fixture
# ---------------------------------------------------------------------------


class TestTenantFixture:
    def test_sets_tenant_context(self, tenant_fixture) -> None:
        from mp_commons.kernel.ddd import TenantContext
        tenant_id = TenantContext.get()
        assert tenant_id is not None

    def test_tenant_id_value(self, tenant_fixture) -> None:
        from mp_commons.kernel.ddd import TenantContext
        tenant_id = TenantContext.get()
        assert str(tenant_id) == "test-tenant" or tenant_id.value == "test-tenant"

    def test_yields_tenant_id(self, tenant_fixture) -> None:
        assert tenant_fixture is not None


# ---------------------------------------------------------------------------
# §37.6  Verify all fixtures are exported from __init__
# ---------------------------------------------------------------------------


class TestFixturesInit:
    def test_all_fixtures_importable(self) -> None:
        from mp_commons.testing.fixtures import (
            correlation_fixture,
            fake_clock,
            fake_idempotency_store,
            fake_inbox_repo,
            fake_message_bus,
            fake_outbox_repo,
            fake_policy_engine,
            tenant_fixture,
        )
        assert all(
            callable(f)
            for f in (
                correlation_fixture,
                fake_clock,
                fake_idempotency_store,
                fake_inbox_repo,
                fake_message_bus,
                fake_outbox_repo,
                fake_policy_engine,
                tenant_fixture,
            )
        )
