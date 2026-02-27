"""Secret rotation primitives."""
from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

__all__ = [
    "DatabasePasswordRotatable",
    "RotatableSecret",
    "RotationScheduler",
    "SecretRotatedEvent",
    "SecretRotator",
]


@runtime_checkable
class RotatableSecret(Protocol):
    """Protocol for any secret that can be rotated."""

    @property
    def secret_name(self) -> str:
        ...

    async def rotate(self) -> str:
        """Generate and persist a new secret value; return the new value."""
        ...

    async def invalidate_old(self, old_value: str) -> None:
        """Revoke / invalidate the previous secret value."""
        ...


@dataclass(frozen=True)
class SecretRotatedEvent:
    secret_name: str
    rotated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SecretRotator:
    """Orchestrates rotation for a collection of registered secrets."""

    def __init__(
        self,
        on_rotated: Callable[[SecretRotatedEvent], Awaitable[None]] | None = None,
    ) -> None:
        self._secrets: list[RotatableSecret] = []
        self._on_rotated = on_rotated
        self.rotation_errors: dict[str, Exception] = {}

    def register(self, secret: RotatableSecret) -> None:
        self._secrets.append(secret)

    async def rotate_all(self) -> list[SecretRotatedEvent]:
        """Rotate every registered secret; isolates per-secret failures."""
        self.rotation_errors = {}
        events: list[SecretRotatedEvent] = []
        for secret in self._secrets:
            try:
                new_value = await secret.rotate()
                event = SecretRotatedEvent(secret_name=secret.secret_name)
                events.append(event)
                if self._on_rotated:
                    await self._on_rotated(event)
            except Exception as exc:  # noqa: BLE001
                self.rotation_errors[secret.secret_name] = exc
        return events


class RotationScheduler:
    """Schedule periodic calls to ``SecretRotator.rotate_all()`` via APScheduler."""

    def __init__(self, rotator: SecretRotator, cron: str = "0 3 * * *") -> None:
        self._rotator = rotator
        self._cron = cron

    def _require_apscheduler(self) -> Any:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            return AsyncIOScheduler
        except ImportError as exc:
            raise ImportError("pip install apscheduler") from exc

    def start(self) -> Any:  # pragma: no cover
        AsyncIOScheduler = self._require_apscheduler()
        scheduler = AsyncIOScheduler()
        parts = self._cron.split()
        if len(parts) == 5:
            minute, hour, day, month, day_of_week = parts
        else:
            minute, hour, day, month, day_of_week = "0", "3", "*", "*", "*"
        scheduler.add_job(
            self._rotator.rotate_all,
            "cron",
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        )
        scheduler.start()
        return scheduler


def _generate_strong_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


class DatabasePasswordRotatable:
    """Rotatable that changes a DB user's password (illustrative implementation)."""

    def __init__(self, user: str, engine: Any | None = None) -> None:
        self._user = user
        self._engine = engine
        self._current: str = ""

    @property
    def secret_name(self) -> str:
        return f"db_password:{self._user}"

    async def rotate(self) -> str:
        new_password = _generate_strong_password()
        if self._engine is not None:  # pragma: no cover
            from sqlalchemy import text
            async with self._engine.begin() as conn:
                await conn.execute(text(f"ALTER USER '{self._user}' IDENTIFIED BY :pw"), {"pw": new_password})
        self._current = new_password
        return new_password

    async def invalidate_old(self, old_value: str) -> None:
        # In real impl: revoke active sessions using old_value
        pass
