"""Testing support – fakes, fixtures, generators, contract helpers, chaos.

Import in your ``conftest.py``::

    pytest_plugins = ["mp_commons.testing.fixtures"]
"""

from mp_commons.testing.fakes import (
    FakeClock,
    FakePolicyEngine,
    InMemoryIdempotencyStore,
    InMemoryInboxRepository,
    InMemoryMessageBus,
    InMemoryOutboxRepository,
)
from mp_commons.testing.generators import (
    correlation_id_gen,
    domain_event_gen,
    email_gen,
    money_gen,
    slug_gen,
    ulid_gen,
)

__all__ = [
    "FakeClock",
    "FakePolicyEngine",
    "InMemoryIdempotencyStore",
    "InMemoryInboxRepository",
    "InMemoryMessageBus",
    "InMemoryOutboxRepository",
    "correlation_id_gen",
    "domain_event_gen",
    "email_gen",
    "money_gen",
    "slug_gen",
    "ulid_gen",
]
