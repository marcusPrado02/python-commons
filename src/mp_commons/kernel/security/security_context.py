"""Kernel security – SecurityContext using contextvars."""

from __future__ import annotations

import contextvars

from mp_commons.kernel.security.principal import Principal

_VAR: contextvars.ContextVar[Principal | None] = contextvars.ContextVar(
    "_security_context", default=None
)


class SecurityContext:
    """Store and retrieve the current authenticated :class:`Principal` via
    :mod:`contextvars` so each asyncio task has its own isolated context."""

    @staticmethod
    def get_current() -> Principal | None:
        """Return the current principal, or ``None`` if absent."""
        return _VAR.get()

    @staticmethod
    def set_current(principal: Principal) -> contextvars.Token[Principal | None]:
        """Set the current principal and return a reset token."""
        return _VAR.set(principal)

    @staticmethod
    def clear() -> None:
        """Remove the current principal from context."""
        _VAR.set(None)

    @staticmethod
    def require() -> Principal:
        """Return the current principal or raise ``UnauthorizedError``."""
        principal = _VAR.get()
        if principal is None:
            from mp_commons.kernel.errors import UnauthorizedError

            raise UnauthorizedError("No authenticated principal in context")
        return principal


__all__ = ["SecurityContext"]
