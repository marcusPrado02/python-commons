"""DomainService marker base class, ServiceRegistry, and @domain_service decorator."""

from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


class DomainService:
    """Marker base for domain services (stateless, operate on entities)."""


# ---------------------------------------------------------------------------
# ServiceRegistry
# ---------------------------------------------------------------------------


class ServiceRegistry:
    """Lightweight in-process service locator.

    Typically one module-level instance is used per bounded context.

    Example::

        registry = ServiceRegistry()

        @domain_service
        class PricingService(DomainService):
            ...

        # Later:
        svc = registry.get("PricingService")
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        """Register *service* under *name* (idempotent for identical objects)."""
        existing = self._store.get(name)
        if existing is not None and existing is not service:
            raise ValueError(
                f"A different service is already registered under {name!r}"
            )
        self._store[name] = service

    def get(self, name: str) -> Any:
        """Return the service registered under *name*.

        Raises ``KeyError`` if not found.
        """
        try:
            return self._store[name]
        except KeyError:
            raise KeyError(f"No service registered under {name!r}") from None

    def get_typed(self, name: str, cls: type[T]) -> T:
        """Return the service registered under *name*, asserting its type.

        Raises ``TypeError`` if the stored service is not an instance of *cls*.
        """
        service = self.get(name)
        if not isinstance(service, cls):
            raise TypeError(
                f"Service {name!r} is {type(service).__name__!r}, "
                f"expected {cls.__name__!r}"
            )
        return service  # type: ignore[return-value]

    def clear(self) -> None:
        """Remove all registrations (useful in tests)."""
        self._store.clear()

    def __contains__(self, name: str) -> bool:
        return name in self._store


# ---------------------------------------------------------------------------
# Module-level default registry + decorator
# ---------------------------------------------------------------------------

_default_registry: ServiceRegistry = ServiceRegistry()


def domain_service(cls: type[T]) -> type[T]:
    """Class decorator — registers *cls* in the module-level ``ServiceRegistry``.

    The class is stored under its ``__name__`` and returned unchanged, so it
    can still be used as a normal class.

    Example::

        @domain_service
        class OrderPricingService(DomainService):
            def calculate(self, order: Order) -> Money:
                ...
    """
    _default_registry.register(cls.__name__, cls)
    return cls


def get_default_registry() -> ServiceRegistry:
    """Return the module-level default service registry."""
    return _default_registry


__all__ = [
    "DomainService",
    "ServiceRegistry",
    "domain_service",
    "get_default_registry",
]