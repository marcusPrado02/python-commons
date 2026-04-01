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
    Builder,
    DataclassBuilder,
    correlation_id_gen,
    domain_event_gen,
    email_gen,
    email_strategy,
    entity_id_strategy,
    money_gen,
    money_strategy,
    slug_gen,
    ulid_gen,
)
from mp_commons.testing.tenant_isolation import TenantIsolationValidator, TenantLeakError

__all__ = [
    "Builder",
    "DataclassBuilder",
    "FakeClock",
    "FakePolicyEngine",
    "InMemoryIdempotencyStore",
    "InMemoryInboxRepository",
    "InMemoryMessageBus",
    "InMemoryOutboxRepository",
    "TenantIsolationValidator",
    "TenantLeakError",
    "correlation_id_gen",
    "domain_event_gen",
    "email_gen",
    "email_strategy",
    "entity_id_strategy",
    "money_gen",
    "money_strategy",
    "slug_gen",
    "ulid_gen",
]
