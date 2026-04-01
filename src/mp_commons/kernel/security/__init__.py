"""Kernel security – Principal, Roles, Permissions, Policy ports, Audit, RBAC."""
from mp_commons.kernel.security.principal import Permission, Principal, Role
from mp_commons.kernel.security.policy import PolicyContext, PolicyDecision, PolicyEngine
from mp_commons.kernel.security.crypto import CryptoProvider, PasswordHasher
from mp_commons.kernel.security.pii import DEFAULT_SENSITIVE_FIELDS, PIIRedactor, RegexPIIRedactor
from mp_commons.kernel.security.security_context import SecurityContext
from mp_commons.kernel.security.audit import AuditEvent, AuditStore, InMemoryAuditStore
from mp_commons.kernel.security.rbac import (
    InMemoryRoleStore,
    RBACPolicy,
    RBACResult,
    RBACRole,
    require_permission,
)
from mp_commons.kernel.security.pkce import (
    PKCEError,
    PKCEVerificationError,
    compute_code_challenge,
    generate_code_verifier,
    generate_pkce_pair,
    verify_code_challenge,
)

__all__ = [
    "AuditEvent",
    "AuditStore",
    "CryptoProvider",
    "DEFAULT_SENSITIVE_FIELDS",
    "InMemoryAuditStore",
    "InMemoryRoleStore",
    "PIIRedactor",
    "PasswordHasher",
    "Permission",
    "PolicyContext",
    "PolicyDecision",
    "PolicyEngine",
    "Principal",
    "RBACPolicy",
    "RBACResult",
    "RBACRole",
    "RegexPIIRedactor",
    "Role",
    "SecurityContext",
    "require_permission",
    # PKCE — RFC 7636
    "PKCEError",
    "PKCEVerificationError",
    "compute_code_challenge",
    "generate_code_verifier",
    "generate_pkce_pair",
    "verify_code_challenge",
]
