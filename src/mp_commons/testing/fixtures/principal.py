"""Testing fixtures – fake_principal and security_context (§37.4)."""
from __future__ import annotations

try:
    import pytest

    @pytest.fixture
    def fake_principal():
        """Return a default :class:`Principal` for test use.

        The principal has subject ``"test-user"``, tenant ``"test-tenant"``,
        and no special roles or permissions.  Override fields in your test::

            def test_something(fake_principal):
                import dataclasses
                p = dataclasses.replace(fake_principal, subject="admin", roles=frozenset(...))
        """
        from mp_commons.kernel.security import Principal
        return Principal(subject="test-user", tenant_id="test-tenant")

    @pytest.fixture
    def security_context(fake_principal):
        """Set *fake_principal* as the current :class:`SecurityContext` for the
        duration of the test and clear it afterwards.

        Usage::

            def test_requires_auth(security_context):
                # SecurityContext.get_current() returns the fake_principal
                ...
        """
        from mp_commons.kernel.security import SecurityContext
        token = SecurityContext.set_current(fake_principal)
        yield fake_principal
        SecurityContext.clear()

except ImportError:
    pass

__all__ = ["fake_principal", "security_context"]
