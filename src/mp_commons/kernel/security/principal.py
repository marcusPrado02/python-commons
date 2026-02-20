"""Kernel security – Principal, Role, Permission."""
from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass(frozen=True)
class Role:
    """Named role (e.g. ADMIN, VIEWER)."""
    name: str

    def __str__(self) -> str:
        return self.name


@dataclasses.dataclass(frozen=True)
class Permission:
    """Fine-grained permission string (e.g. 'orders:write')."""
    value: str

    def __str__(self) -> str:
        return self.value


@dataclasses.dataclass(frozen=True)
class Principal:
    """Authenticated identity."""
    subject: str
    tenant_id: str | None = None
    roles: frozenset[Role] = frozenset()
    permissions: frozenset[Permission] = frozenset()
    claims: dict[str, Any] = dataclasses.field(default_factory=dict)
    is_service_account: bool = False

    def has_role(self, role: str | Role) -> bool:
        name = role.name if isinstance(role, Role) else role
        return any(r.name == name for r in self.roles)

    def has_permission(self, permission: str | Permission) -> bool:
        value = permission.value if isinstance(permission, Permission) else permission
        return any(p.value == value for p in self.permissions)


__all__ = ["Permission", "Principal", "Role"]
