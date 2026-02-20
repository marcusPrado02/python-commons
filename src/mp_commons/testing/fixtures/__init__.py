"""Testing fixtures – pytest fixtures for fake doubles."""
try:
    import pytest  # noqa: F401

    from mp_commons.testing.fixtures.clock import fake_clock
    from mp_commons.testing.fixtures.message_bus import (
        fake_idempotency_store,
        fake_inbox_repo,
        fake_message_bus,
        fake_outbox_repo,
    )
    from mp_commons.testing.fixtures.security import fake_policy_engine
    from mp_commons.testing.fixtures.correlation import correlation_fixture
    from mp_commons.testing.fixtures.tenant import tenant_fixture

    def pytest_plugins() -> list[str]:
        return ["mp_commons.testing.fixtures"]

except ImportError:
    pass

__all__ = [
    "correlation_fixture",
    "fake_clock",
    "fake_idempotency_store",
    "fake_inbox_repo",
    "fake_message_bus",
    "fake_outbox_repo",
    "fake_policy_engine",
    "pytest_plugins",
    "tenant_fixture",
]
