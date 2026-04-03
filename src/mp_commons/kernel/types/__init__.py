"""Kernel value-object types — public re-export surface.

Provides EntityId, TenantId, CorrelationId, TraceId, UserId, ULID, UUIDv7,
Money, Email, PhoneNumber, Slug, Ok, Err, Result, Some, Nothing, Option.
"""

from mp_commons.kernel.types.email import Email
from mp_commons.kernel.types.ids import (
    CorrelationId,
    EntityId,
    TenantId,
    TraceId,
    UserId,
)
from mp_commons.kernel.types.money import Money
from mp_commons.kernel.types.option import Nothing, Option, Some
from mp_commons.kernel.types.phone import PhoneNumber
from mp_commons.kernel.types.result import Err, Ok, Result
from mp_commons.kernel.types.slug import Slug
from mp_commons.kernel.types.uid import UID, ULID, UUIDv7

__all__ = [
    "UID",
    "ULID",
    "CorrelationId",
    "Email",
    "EntityId",
    "Err",
    "Money",
    "Nothing",
    "Ok",
    "Option",
    "PhoneNumber",
    "Result",
    "Slug",
    "Some",
    "TenantId",
    "TraceId",
    "UUIDv7",
    "UserId",
]
