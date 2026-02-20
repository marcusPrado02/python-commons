"""Kernel security – PolicyDecision, PolicyContext, PolicyEngine."""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any, Protocol

from mp_commons.kernel.security.principal import Principal


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclasses.dataclass(frozen=True)
class PolicyContext:
    """Context passed to the policy engine for evaluation."""
    principal: Principal
    resource: str
    action: str
    attributes: dict[str, Any] = dataclasses.field(default_factory=dict)


class PolicyEngine(Protocol):
    """Port: evaluate access-control policies."""

    async def evaluate(self, context: PolicyContext) -> PolicyDecision: ...


__all__ = ["PolicyContext", "PolicyDecision", "PolicyEngine"]
