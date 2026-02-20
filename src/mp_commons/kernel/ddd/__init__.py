"""DDD building blocks — public re-export surface.

Modules:
  value_object.py  — ValueObject
  entity.py        — Entity
  domain_event.py  — DomainEvent, DomainEventEnvelope, EventSourcingSnapshot
  aggregate.py     — AggregateRoot
  invariant.py     — Invariant, ensure
  specification.py — Specification, AndSpecification, OrSpecification, NotSpecification
  repository.py        — Repository
  unit_of_work.py      — UnitOfWork
  domain_service.py    — DomainService
  tenant.py            — TenantContext, TenantResolver
  outbox_publisher.py  — OutboxPublisher
  event_bus.py         — DomainEventBus
  saga.py              — Saga
"""

from mp_commons.kernel.ddd.aggregate import AggregateRoot
from mp_commons.kernel.ddd.domain_event import (
    DomainEvent,
    DomainEventEnvelope,
    EventSourcingSnapshot,
)
from mp_commons.kernel.ddd.domain_service import DomainService
from mp_commons.kernel.ddd.entity import Entity
from mp_commons.kernel.ddd.invariant import Invariant, ensure
from mp_commons.kernel.ddd.repository import Repository
from mp_commons.kernel.ddd.event_bus import DomainEventBus
from mp_commons.kernel.ddd.outbox_publisher import OutboxPublisher
from mp_commons.kernel.ddd.saga import Saga
from mp_commons.kernel.ddd.specification import (
    AndSpecification,
    BaseSpecification,
    NotSpecification,
    OrSpecification,
    Specification,
)
from mp_commons.kernel.ddd.tenant import TenantContext, TenantResolver
from mp_commons.kernel.ddd.unit_of_work import UnitOfWork
from mp_commons.kernel.ddd.value_object import ValueObject

__all__ = [
    "AggregateRoot",
    "AndSpecification",
    "BaseSpecification",
    "DomainEvent",
    "DomainEventBus",
    "DomainEventEnvelope",
    "DomainService",
    "Entity",
    "EventSourcingSnapshot",
    "Invariant",
    "NotSpecification",
    "OrSpecification",
    "OutboxPublisher",
    "Repository",
    "Saga",
    "Specification",
    "TenantContext",
    "TenantResolver",
    "UnitOfWork",
    "ValueObject",
    "ensure",
]
