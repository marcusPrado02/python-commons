"""Test helper for multi-tenant isolation validation (S-01).

:class:`TenantIsolationValidator` wraps a repository and verifies that every
result returned belongs to the **current** tenant.  Use it in tests to catch
cross-tenant data leakage.

Usage::

    from mp_commons.testing.tenant_isolation import TenantIsolationValidator
    from mp_commons.kernel.ddd.tenant import TenantContext
    from mp_commons.kernel.types.ids import TenantId

    # In a pytest fixture or test:
    repo = MyOrderRepository(session)
    safe_repo = TenantIsolationValidator(repo, tenant_id=TenantId("acme"))

    async with TenantContext.scoped(TenantId("acme")):
        orders = await safe_repo.find_all()  # passes: all orders belong to "acme"

    # If the underlying repo leaks tenant "other-org":
    # TenantLeakError: found 2 result(s) belonging to other tenant(s): {'other-org'}
"""

from __future__ import annotations

import functools
import inspect
from typing import Any


class TenantLeakError(AssertionError):
    """Raised when a repository returns objects belonging to a different tenant.

    Attributes
    ----------
    expected_tenant:
        The tenant that was in scope during the query.
    leaked_tenants:
        Set of tenant IDs found in the result that do not match
        *expected_tenant*.
    """

    def __init__(
        self,
        expected_tenant: str,
        leaked_tenants: set[str],
        count: int,
    ) -> None:
        super().__init__(
            f"TenantLeakError: found {count} result(s) belonging to other "
            f"tenant(s): {leaked_tenants!r}. Expected only: {expected_tenant!r}"
        )
        self.expected_tenant = expected_tenant
        self.leaked_tenants = leaked_tenants


class TenantIsolationValidator:
    """Repository proxy that validates tenant isolation on every returned value.

    Wraps any repository object and intercepts all methods that return a list
    or a single domain object.  After each call it inspects the result(s) for a
    ``tenant_id`` attribute and raises :class:`TenantLeakError` if any value
    belongs to a different tenant.

    Parameters
    ----------
    repository:
        The real repository instance to delegate calls to.
    tenant_id:
        The expected ``TenantId`` (or its string representation).
    attr:
        Name of the attribute on domain objects that holds the tenant ID.
        Defaults to ``"tenant_id"``.

    Example::

        validator = TenantIsolationValidator(order_repo, tenant_id="acme")
        orders = await validator.find_all()
    """

    def __init__(
        self,
        repository: Any,
        tenant_id: Any,
        *,
        attr: str = "tenant_id",
    ) -> None:
        self._repo = repository
        self._expected = str(tenant_id)
        self._attr = attr

    def _validate(self, result: Any) -> None:
        """Inspect *result* (single item or iterable) for tenant leakage."""
        items: list[Any] = []
        if result is None:
            return
        if isinstance(result, (list, tuple)) or (
            hasattr(result, "__iter__") and not isinstance(result, (str, bytes, dict))
        ):
            items = list(result)
        else:
            items = [result]

        leaked: set[str] = set()
        for item in items:
            tid = getattr(item, self._attr, None)
            if tid is not None and str(tid) != self._expected:
                leaked.add(str(tid))

        if leaked:
            raise TenantLeakError(
                expected_tenant=self._expected,
                leaked_tenants=leaked,
                count=sum(
                    1
                    for item in items
                    if getattr(item, self._attr, None) is not None
                    and str(getattr(item, self._attr)) != self._expected
                ),
            )

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._repo, name)
        if not callable(attr):
            return attr

        if inspect.iscoroutinefunction(attr):

            @functools.wraps(attr)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                result = await attr(*args, **kwargs)
                self._validate(result)
                return result

            return _async_wrapper

        @functools.wraps(attr)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = attr(*args, **kwargs)
            self._validate(result)
            return result

        return _sync_wrapper


__all__ = ["TenantIsolationValidator", "TenantLeakError"]
