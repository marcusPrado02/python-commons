"""Application pipeline – AuditMiddleware."""

from __future__ import annotations

from typing import Any

from mp_commons.application.pipeline.middleware import Middleware, Next
from mp_commons.kernel.security.audit import AuditEvent, AuditStore
from mp_commons.kernel.security.security_context import SecurityContext


class AuditMiddleware(Middleware):
    """Pipeline middleware that automatically records an :class:`AuditEvent`
    after every command/query passes through the chain.

    The ``principal_id`` is read from
    :class:`~mp_commons.kernel.security.SecurityContext`.  If no principal is
    found the event is still recorded with ``principal_id="anonymous"``.

    Outcome is determined by whether the inner chain raises an exception:

    - No exception → ``"allow"``
    - Exception raised → ``"deny"`` (exception is re-raised after recording)

    By default ``resource_type`` is the class name of the request and
    ``resource_id`` is taken from ``request.id`` if present, otherwise
    ``"-"``.

    Usage::

        pipeline = Pipeline([
            AuditMiddleware(
                store=audit_store,
                action="orders:command",
            ),
        ], handler=bus.dispatch)
    """

    def __init__(
        self,
        store: AuditStore,
        *,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> None:
        self._store = store
        self._action = action
        self._resource_type = resource_type

    async def __call__(self, request: Any, next_: Next) -> Any:
        principal = SecurityContext.get_current()
        principal_id = principal.subject if principal is not None else "anonymous"

        action = self._action or type(request).__name__
        resource_type = self._resource_type or type(request).__name__
        resource_id: str = str(getattr(request, "id", "-"))

        outcome: str = "allow"
        exc_to_raise: BaseException | None = None

        try:
            result = await next_(request)
        except Exception as exc:
            outcome = "deny"
            exc_to_raise = exc
            result = None

        event = AuditEvent(
            principal_id=principal_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,  # type: ignore[arg-type]
        )
        await self._store.record(event)

        if exc_to_raise is not None:
            raise exc_to_raise

        return result


__all__ = ["AuditMiddleware"]
