"""Testing fakes – in-memory doubles for kernel ports."""
from mp_commons.testing.fakes.clock import FakeClock
from mp_commons.testing.fakes.message_bus import InMemoryMessageBus
from mp_commons.testing.fakes.outbox import InMemoryOutboxRepository
from mp_commons.testing.fakes.inbox import InMemoryInboxRepository
from mp_commons.testing.fakes.idempotency import InMemoryIdempotencyStore
from mp_commons.testing.fakes.policy import FakePolicyEngine
from mp_commons.kernel.time import FrozenClock

__all__ = [
    "FakeClock",
    "FakePolicyEngine",
    "FrozenClock",
    "InMemoryIdempotencyStore",
    "InMemoryInboxRepository",
    "InMemoryMessageBus",
    "InMemoryOutboxRepository",
]
