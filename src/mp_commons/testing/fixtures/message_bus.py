"""Testing fixtures – fake_message_bus, fake_outbox_repo, fake_idempotency_store."""
from __future__ import annotations

try:
    import pytest

    @pytest.fixture
    def fake_message_bus():
        from mp_commons.testing.fakes import InMemoryMessageBus
        return InMemoryMessageBus()

    @pytest.fixture
    def fake_outbox_repo():
        from mp_commons.testing.fakes import InMemoryOutboxRepository
        return InMemoryOutboxRepository()

    @pytest.fixture
    def fake_inbox_repo():
        from mp_commons.testing.fakes import InMemoryInboxRepository
        return InMemoryInboxRepository()

    @pytest.fixture
    def fake_idempotency_store():
        from mp_commons.testing.fakes import InMemoryIdempotencyStore
        return InMemoryIdempotencyStore()

except ImportError:
    pass

__all__ = ["fake_idempotency_store", "fake_inbox_repo", "fake_message_bus", "fake_outbox_repo"]
