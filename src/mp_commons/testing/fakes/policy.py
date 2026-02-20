"""Testing fakes – FakePolicyEngine."""
from __future__ import annotations

from mp_commons.kernel.security import PolicyContext, PolicyDecision, PolicyEngine


class FakePolicyEngine(PolicyEngine):
    """Configurable policy engine for tests.

    By default every request is ALLOWED.  Override with::

        engine.set(resource="orders", action="create", decision=PolicyDecision.DENY)
    """

    def __init__(self) -> None:
        self._overrides: dict[tuple[str, str], PolicyDecision] = {}
        self._default = PolicyDecision.ALLOW

    def set(self, resource: str, action: str, decision: PolicyDecision) -> None:
        self._overrides[(resource, action)] = decision

    def deny_all(self) -> None:
        self._default = PolicyDecision.DENY

    def allow_all(self) -> None:
        self._default = PolicyDecision.ALLOW

    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        key = (context.resource, context.action)
        return self._overrides.get(key, self._default)


__all__ = ["FakePolicyEngine"]
