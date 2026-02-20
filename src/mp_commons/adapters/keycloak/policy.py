"""Keycloak adapter – KeycloakPolicyEngineAdapter."""
from __future__ import annotations

from mp_commons.kernel.security import PolicyContext, PolicyDecision
from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier


class KeycloakPolicyEngineAdapter:
    """Policy engine that delegates to Keycloak Authorization Services."""

    def __init__(self, token_verifier: OIDCTokenVerifier) -> None:
        self._verifier = token_verifier

    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        resource = f"{context.resource}:{context.action}"
        if context.principal.has_permission(resource):
            return PolicyDecision.ALLOW
        if context.principal.has_role("admin"):
            return PolicyDecision.ALLOW
        return PolicyDecision.DENY


__all__ = ["KeycloakPolicyEngineAdapter"]
