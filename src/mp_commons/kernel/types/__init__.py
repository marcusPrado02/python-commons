"""Kernel value-object types — public re-export surface.

Modules:
  ids.py    — EntityId, TenantId, CorrelationId, TraceId, UserId
  uid.py    — ULID, UUIDv7
  money.py  — Money
  email.py  — Email
  phone.py  — PhoneNumber
  slug.py   — Slug
  result.py — Ok, Err, Result
  option.py — Some, Nothing, Option
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
from mp_commons.kernel.types.uid import ULID, UUIDv7

__all__ = [
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
    "ULID",
    "UUIDv7",
    "UserId",
]
