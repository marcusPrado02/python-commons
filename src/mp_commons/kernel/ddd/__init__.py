"""DDD building blocks — public re-export surface."""

from mp_commons.kernel.ddd.aggregate import AggregateRoot
from mp_commons.kernel.ddd.domain_event import (
    DomainEvent,
    DomainEventEnvelope,
    EventSourcingSnapshot,
)
from mp_commons.kernel.ddd.domain_service import (
    DomainService,
    ServiceRegistry,
    domain_service,
    get_default_registry,
)
from mp_commons.kernel.ddd.entity import Entity
from mp_commons.kernel.ddd.invariant import Invariant, ensure
from mp_commons.kernel.ddd.policies import (
    AllOf,
    AnyOf,
    ExpiryPolicy,
    NoneOf,
    Policy,
    PolicyResult,
)
from mp_commons.kernel.ddd.repository import Repository
from mp_commons.kernel.ddd.event_bus import DomainEventBus
from mp_commons.kernel.ddd.outbox_publisher import OutboxPublisher
from mp_commons.kernel.ddd.saga import Saga
from mp_commons.kernel.ddd.specification import (
    AndSpecification,
    BaseSpecification,
    LambdaSpecification,
    NotSpecification,
    OrSpecification,
    Specification,
)
from mp_commons.kernel.ddd.tenant import TenantAware, TenantContext, TenantResolver
from mp_commons.kernel.ddd.unit_of_work import UnitOfWork
from mp_commons.kernel.ddd.value_object import ValueObject

__all__ = [
    "AggregateRoot",
    "AllOf",
    "AndSpecification",
    "AnyOf",
    "BaseSpecification",
    "DomainEvent",
    "DomainEventBus",
    "DomainEventEnvelope",
    "DomainService",
    "Entity",
    "EventSourcingSnapshot",
    "ExpiryPolicy",
    "Invariant",
    "LambdaSpecification",
    "NoneOf",
    "NotSpecification",
    "OrSpecification",
    "OutboxPublisher",
    "Policy",
    "PolicyResult",
    "Repository",
    "Saga",
    "ServiceRegistry",
    "Specification",
    "TenantAware",
    "TenantContext",
    "TenantResolver",
    "UnitOfWork",
    "ValueObject",
    "domain_service",
    "ensure",
    "get_default_registry",
]
