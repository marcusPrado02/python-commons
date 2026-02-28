"""SQLAlchemy TenantFilter — §61.5.

Registers SQLAlchemy ``before_compile`` event listeners that automatically
append ``WHERE tenant_id = :_mpct_tid`` to every ``SELECT``, ``UPDATE``, and
``DELETE`` statement that targets a :class:`~mp_commons.kernel.ddd.tenant.TenantAware`
mapped class.

Activation::

    from mp_commons.adapters.sqlalchemy.tenant_filter import TenantFilter

    TenantFilter.install()          # once, at application start-up

Deactivation (useful in tests)::

    TenantFilter.uninstall()

If the current :class:`~mp_commons.kernel.ddd.tenant.TenantContext` is empty
(i.e. no tenant set) the statement is *not* modified so that administrative /
background tasks can still access cross-tenant data.

Requires SQLAlchemy ≥ 2.0.
"""
from __future__ import annotations

from typing import Any

_installed: bool = False


def _require_sqlalchemy() -> None:
    try:
        import sqlalchemy  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "sqlalchemy is required for TenantFilter. "
            "Install it with: pip install 'sqlalchemy>=2.0'"
        ) from exc


# ---------------------------------------------------------------------------
# Core listener
# ---------------------------------------------------------------------------


def _before_compile_handler(query: Any) -> None:  # pragma: no branch
    """Inject tenant_id WHERE clause when TenantContext is set."""
    from mp_commons.kernel.ddd.tenant import TenantAware, TenantContext

    tenant_id = TenantContext.get()
    if tenant_id is None:
        return  # no tenant in context — allow unrestricted access

    try:
        from sqlalchemy import inspect, literal  # type: ignore[import-untyped]
        from sqlalchemy.orm import Query  # type: ignore[import-untyped]
    except ImportError:
        return

    # Determine the primary entity of the query
    column_descriptions = getattr(query, "column_descriptions", [])
    if not column_descriptions:
        return

    entity = column_descriptions[0].get("entity")
    if entity is None:
        return

    # Only filter TenantAware models
    try:
        mapper = inspect(entity)
        if not issubclass(entity, TenantAware):
            return
        # Check that 'tenant_id' is actually a mapped column
        if "tenant_id" not in {c.key for c in mapper.mapper.column_attrs}:
            return
    except Exception:
        return

    query = query.enable_assertions(False).filter(
        entity.tenant_id == literal(str(tenant_id))
    )


# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------


class TenantFilter:
    """Namespace for install/uninstall of the SQLAlchemy tenant filter.

    Usage::

        TenantFilter.install()    # registers the event once
        TenantFilter.uninstall()  # removes the event
    """

    @staticmethod
    def install() -> None:
        """Register the ``before_compile`` query event globally.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        global _installed  # noqa: PLW0603
        if _installed:
            return
        _require_sqlalchemy()
        from sqlalchemy.orm import Query  # type: ignore[import-untyped]
        from sqlalchemy import event  # type: ignore[import-untyped]

        event.listen(Query, "before_compile", _before_compile_handler, retval=False)
        _installed = True

    @staticmethod
    def uninstall() -> None:
        """Remove the ``before_compile`` query event.

        Safe to call even when not installed.
        """
        global _installed  # noqa: PLW0603
        if not _installed:
            return
        try:
            from sqlalchemy.orm import Query  # type: ignore[import-untyped]
            from sqlalchemy import event  # type: ignore[import-untyped]

            event.remove(Query, "before_compile", _before_compile_handler)
        except Exception:
            pass
        _installed = False

    @staticmethod
    def is_installed() -> bool:
        """Return ``True`` when the filter event is currently registered."""
        return _installed


__all__ = ["TenantFilter"]
