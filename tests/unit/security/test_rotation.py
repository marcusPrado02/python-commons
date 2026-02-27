"""Unit tests for §88 – Secret Rotation."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from mp_commons.security.rotation import (
    DatabasePasswordRotatable,
    RotatableSecret,
    SecretRotatedEvent,
    SecretRotator,
)


@dataclass
class _FakeSecret:
    _name: str
    _rotated_values: list = None
    _fail: bool = False

    def __post_init__(self):
        if self._rotated_values is None:
            self._rotated_values = []

    @property
    def secret_name(self) -> str:
        return self._name

    async def rotate(self) -> str:
        if self._fail:
            raise RuntimeError("rotation failed")
        new_value = f"new-value-{len(self._rotated_values)}"
        self._rotated_values.append(new_value)
        return new_value

    async def invalidate_old(self, old_value: str) -> None:
        pass


class TestSecretRotator:
    def test_rotate_all_calls_all_secrets(self):
        s1 = _FakeSecret("db1")
        s2 = _FakeSecret("db2")
        rotator = SecretRotator()
        rotator.register(s1)
        rotator.register(s2)
        events = asyncio.run(rotator.rotate_all())
        assert len(events) == 2
        assert s1._rotated_values == ["new-value-0"]
        assert s2._rotated_values == ["new-value-0"]

    def test_rotate_all_returns_events(self):
        s = _FakeSecret("svc")
        rotator = SecretRotator()
        rotator.register(s)
        events = asyncio.run(rotator.rotate_all())
        assert len(events) == 1
        assert isinstance(events[0], SecretRotatedEvent)
        assert events[0].secret_name == "svc"

    def test_rotate_failure_is_isolated(self):
        ok = _FakeSecret("ok")
        bad = _FakeSecret("bad", _fail=True)
        rotator = SecretRotator()
        rotator.register(ok)
        rotator.register(bad)
        events = asyncio.run(rotator.rotate_all())
        assert len(events) == 1
        assert events[0].secret_name == "ok"
        assert "bad" in rotator.rotation_errors
        assert isinstance(rotator.rotation_errors["bad"], RuntimeError)

    def test_on_rotated_callback_called(self):
        received = []

        async def callback(event: SecretRotatedEvent) -> None:
            received.append(event)

        rotator = SecretRotator(on_rotated=callback)
        rotator.register(_FakeSecret("x"))
        asyncio.run(rotator.rotate_all())
        assert len(received) == 1

    def test_rotate_all_empty_registry(self):
        rotator = SecretRotator()
        events = asyncio.run(rotator.rotate_all())
        assert events == []


class TestDatabasePasswordRotatable:
    def test_secret_name(self):
        r = DatabasePasswordRotatable("myuser")
        assert r.secret_name == "db_password:myuser"

    def test_rotate_returns_new_password(self):
        r = DatabasePasswordRotatable("user1")
        new_val = asyncio.run(r.rotate())
        assert isinstance(new_val, str)
        assert len(new_val) >= 16

    def test_rotate_different_values(self):
        r = DatabasePasswordRotatable("user2")
        v1 = asyncio.run(r.rotate())
        v2 = asyncio.run(r.rotate())
        assert v1 != v2

    def test_invalidate_old_no_error(self):
        r = DatabasePasswordRotatable("user3")
        asyncio.run(r.invalidate_old("old-password"))


class TestRotatableSecretProtocol:
    def test_protocol_check(self):
        s = _FakeSecret("a")
        assert isinstance(s, RotatableSecret)


class TestRotationScheduler:
    def test_scheduler_raises_without_apscheduler(self):
        from mp_commons.security.rotation.rotator import RotationScheduler
        rotator = SecretRotator()
        scheduler = RotationScheduler(rotator)
        with pytest.raises(ImportError, match="apscheduler"):
            scheduler._require_apscheduler()
