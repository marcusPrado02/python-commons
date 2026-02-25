"""Kernel security — Role-Based Access Control (RBAC).

Builds on top of the existing :class:`~mp_commons.kernel.security.principal.Permission`
and :class:`~mp_commons.kernel.security.principal.Principal` without breaking
their interfaces.

Key additions:
* :class:`RBACRole` — an enriched role that bundles a set of :class:`Permission`\\ s.
* :class:`RBACPolicy` — evaluates whether the current principal holds a required permission.
* :func:`require_permission` — decorator for command / query handlers.
* :class:`InMemoryRoleStore` — test-friendly role store.
"""

from __future__ import annotations

import dataclasses
import functools
import inspect
from typing import Any, Callable, TypeVar

from mp_commons.kernel.errors.application import ForbiddenError, UnauthorizedError
from mp_commons.kernel.security.principal import Permission, Principal
from mp_commons.kernel.security.security_context import SecurityContext

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Wildcard matching helper
# ---------------------------------------------------------------------------


def _permission_matches(stored: str, required: str) -> bool:
    """Return ``True`` if *stored* satisfies *required* permission.

    Wildcard rules:
    - ``"*"`` matches any permission.
    - ``"resource:*"`` matches any action on *resource*.
    - Exact string match also satisfies.
    """
    if stored == "*":
        return True
    if stored == required:
        return True
    # "resource:*" matches "resource:action"
    if stored.endswith(":*"):
        prefix = stored[:-1]  # "resource:"
        return required.startswith(prefix)
    return False


# ---------------------------------------------------------------------------
# RBACRole
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RBACRole:
    """A named role that carries an explicit set of :class:`Permission`\\ s.

    Unlike the lightweight :class:`~mp_commons.kernel.security.principal.Role`
    (which only has a name), ``RBACRole`` is used for fine-grained permission
    checks.

    Example::

        editor = RBACRole(
            name="editor",
            permissions=frozenset({
                Permission("articles:read"),
                Permission("articles:write"),
                Permission("articles:delete"),
            }),
        )
    """

    name: str
    permissions: frozenset[Permission] = dataclasses.field(
        default_factory=frozenset
    )

    def has_permission(self, perm: Permission | str) -> bool:
        """Return ``True`` if this role grants *perm* (supports wildcard)."""
        required = perm.value if isinstance(perm, Permission) else perm
        return any(
            _permission_matches(p.value, required) for p in self.permissions
        )


# ---------------------------------------------------------------------------
# InMemoryRoleStore
# ---------------------------------------------------------------------------


class InMemoryRoleStore:
    """Simple in-process mapping of principal IDs to :class:`RBACRole`\\ s.

    Intended for unit tests and small applications.  Thread-safe operations
    use plain dict; for async safety use it from a single coroutine.
    """

    def __init__(self) -> None:
        self._store: dict[str, set[RBACRole]] = {}

    def add_role(self, principal_id: str, role: RBACRole) -> None:
        """Assign *role* to *principal_id*."""
        self._store.setdefault(principal_id, set()).add(role)

    def remove_role(self, principal_id: str, role: RBACRole) -> None:
        """Remove *role* from *principal_id* (no-op if not present)."""
        if principal_id in self._store:
            self._store[principal_id].discard(role)

    def get_roles(self, principal_id: str) -> list[RBACRole]:
        """Return all roles assigned to *principal_id*."""
        return list(self._store.get(principal_id, set()))

    def has_permission(self, principal_id: str, perm: Permission | str) -> bool:
        """Quick check: does *principal_id* hold *perm* via any role?"""
        return any(r.has_permission(perm) for r in self.get_roles(principal_id))

    def clear(self) -> None:
        """Remove all assignments (useful between tests)."""
        self._store.clear()


# ---------------------------------------------------------------------------
# RBACPolicy
# ---------------------------------------------------------------------------


class RBACPolicy:
    """Checks whether the current :class:`~.SecurityContext` principal holds a
    required permission.

    Permission resolution order:

    1. ``principal.permissions`` — direct permission set on the principal.
    2. ``role_store`` (if provided) — per-principal :class:`RBACRole`\\ s.

    Wildcard permissions are honoured at both levels.

    Example::

        policy = RBACPolicy(Permission("orders:cancel"), role_store=store)
        result = policy.evaluate(SecurityContext.require())
        if not result.allowed:
            raise ForbiddenError(result.reason)
    """

    def __init__(
        self,
        required: Permission | str,
        *,
        role_store: InMemoryRoleStore | None = None,
    ) -> None:
        self._required = (
            required if isinstance(required, Permission) else Permission(required)
        )
        self._role_store = role_store

    def evaluate(self, principal: Principal) -> "RBACResult":
        """Evaluate *principal* against the required permission."""
        req = self._required.value

        # 1. Direct permission on the Principal
        if any(
            _permission_matches(p.value, req) for p in principal.permissions
        ):
            return RBACResult(allowed=True, principal=principal)

        # 2. Via role store (if provided)
        if self._role_store is not None:
            if self._role_store.has_permission(principal.subject, self._required):
                return RBACResult(allowed=True, principal=principal)

        return RBACResult(
            allowed=False,
            principal=principal,
            missing_permission=self._required,
        )


@dataclasses.dataclass(frozen=True)
class RBACResult:
    """Result of an :class:`RBACPolicy` evaluation."""

    allowed: bool
    principal: Principal
    missing_permission: Permission | None = None

    @property
    def reason(self) -> str | None:
        if not self.allowed and self.missing_permission is not None:
            return (
                f"principal {self.principal.subject!r} lacks "
                f"permission {self.missing_permission.value!r}"
            )
        return None

    def __bool__(self) -> bool:
        return self.allowed


# ---------------------------------------------------------------------------
# @require_permission decorator
# ---------------------------------------------------------------------------


def require_permission(
    perm: Permission | str,
    *,
    role_store: InMemoryRoleStore | None = None,
) -> Callable[[F], F]:
    """Decorator that enforces *perm* on the current :class:`SecurityContext`.

    Works on both async and sync callables.  Raises :class:`UnauthorizedError`
    if there is no principal in context, and :class:`ForbiddenError` if the
    principal lacks the required permission.

    Example::

        @require_permission("orders:cancel")
        async def cancel_order(cmd: CancelOrderCommand) -> None:
            ...
    """
    policy = RBACPolicy(perm, role_store=role_store)

    def decorator(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                principal = SecurityContext.require()  # raises UnauthorizedError if absent
                result = policy.evaluate(principal)
                if not result.allowed:
                    raise ForbiddenError(result.reason or "forbidden")
                return await fn(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            principal = SecurityContext.require()
            result = policy.evaluate(principal)
            if not result.allowed:
                raise ForbiddenError(result.reason or "forbidden")
            return fn(*args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator  # type: ignore[return-value]


__all__ = [
    "InMemoryRoleStore",
    "RBACPolicy",
    "RBACResult",
    "RBACRole",
    "require_permission",
]
