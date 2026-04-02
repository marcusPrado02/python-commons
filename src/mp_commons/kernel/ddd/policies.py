"""Domain Policy Pattern — composable business rule evaluators.

A ``Policy`` encapsulates a decision rule that operates on a typed context and
returns a ``PolicyResult`` (allowed/denied with optional reason).  Policies can
be composed with ``AllOf``, ``AnyOf``, and ``NoneOf``.

This module is intentionally named *policies* (plural) to avoid colliding with
``mp_commons.kernel.security.policy`` which provides the ABAC/AuthZ port.

Example::

    class AgePolicy(Policy[User]):
        def evaluate(self, ctx: User) -> PolicyResult:
            return PolicyResult(ctx.age >= 18, reason="must be adult")


    policy = AllOf(AgePolicy(), VerifiedEmailPolicy())
    result = policy.evaluate(user)
    if not result.allowed:
        raise DomainError(result.reason)
"""

from __future__ import annotations

import abc
import dataclasses
from datetime import datetime
from typing import Generic, TypeVar

TContext = TypeVar("TContext")


# ---------------------------------------------------------------------------
# PolicyResult
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PolicyResult:
    """Outcome of a policy evaluation.

    Attributes:
        allowed: ``True`` when the policy permits the action.
        reason: Human-readable explanation (populated especially on denial).
    """

    allowed: bool
    reason: str | None = None

    # Convenience factories -----------------------------------------------

    @classmethod
    def permit(cls, reason: str | None = None) -> PolicyResult:
        return cls(allowed=True, reason=reason)

    @classmethod
    def deny(cls, reason: str = "denied") -> PolicyResult:
        return cls(allowed=False, reason=reason)

    def __bool__(self) -> bool:  # allows ``if policy.evaluate(ctx):``
        return self.allowed


# ---------------------------------------------------------------------------
# Policy base
# ---------------------------------------------------------------------------


class Policy(abc.ABC, Generic[TContext]):
    """Abstract policy evaluated against a typed context."""

    @abc.abstractmethod
    def evaluate(self, context: TContext) -> PolicyResult: ...


# ---------------------------------------------------------------------------
# Composite policies
# ---------------------------------------------------------------------------


class AllOf(Policy[TContext]):
    """Conjunction: every policy must allow. Short-circuits on first denial."""

    def __init__(self, *policies: Policy[TContext]) -> None:
        if not policies:
            raise ValueError("AllOf requires at least one policy")
        self._policies = policies

    def evaluate(self, context: TContext) -> PolicyResult:
        for p in self._policies:
            result = p.evaluate(context)
            if not result.allowed:
                return result
        return PolicyResult.permit()


class AnyOf(Policy[TContext]):
    """Disjunction: at least one policy must allow. Short-circuits on first permit."""

    def __init__(self, *policies: Policy[TContext]) -> None:
        if not policies:
            raise ValueError("AnyOf requires at least one policy")
        self._policies = policies

    def evaluate(self, context: TContext) -> PolicyResult:
        last_denial = PolicyResult.deny("all policies denied")
        for p in self._policies:
            result = p.evaluate(context)
            if result.allowed:
                return result
            last_denial = result
        return last_denial


class NoneOf(Policy[TContext]):
    """NOR: all policies must *deny*. Fails if any policy permits."""

    def __init__(self, *policies: Policy[TContext]) -> None:
        if not policies:
            raise ValueError("NoneOf requires at least one policy")
        self._policies = policies

    def evaluate(self, context: TContext) -> PolicyResult:
        for p in self._policies:
            result = p.evaluate(context)
            if result.allowed:
                return PolicyResult.deny(f"policy was allowed but NoneOf forbids: {result.reason}")
        return PolicyResult.permit()


# ---------------------------------------------------------------------------
# Built-in policies
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _TimestampedContext:
    """Minimal protocol: any context with a ``timestamp`` attribute."""

    timestamp: datetime


class ExpiryPolicy(Policy[_TimestampedContext]):
    """Allows evaluation only within a configured time window.

    Args:
        not_before: Earliest allowed timestamp (inclusive).  ``None`` = no lower bound.
        not_after:  Latest allowed timestamp (inclusive).  ``None`` = no upper bound.

    The context object must expose a ``timestamp: datetime`` attribute.
    """

    def __init__(
        self,
        *,
        not_before: datetime | None = None,
        not_after: datetime | None = None,
    ) -> None:
        self._not_before = not_before
        self._not_after = not_after

    def evaluate(self, context: _TimestampedContext) -> PolicyResult:  # type: ignore[override]
        ts = context.timestamp
        if self._not_before is not None and ts < self._not_before:
            return PolicyResult.deny(
                f"timestamp {ts.isoformat()} is before {self._not_before.isoformat()}"
            )
        if self._not_after is not None and ts > self._not_after:
            return PolicyResult.deny(
                f"timestamp {ts.isoformat()} is after {self._not_after.isoformat()}"
            )
        return PolicyResult.permit()


# ---------------------------------------------------------------------------
# §59.4 – QuotaPolicy
# ---------------------------------------------------------------------------


class QuotaPolicy(Policy["_RateLimitResult"]):
    """Evaluates whether a :class:`~mp_commons.application.rate_limit.RateLimitResult`
    reports remaining capacity.

    Delegates the decision to the ``RateLimitResult`` already obtained from a
    :class:`~mp_commons.application.rate_limit.RateLimiter`.  The async
    ``RateLimiter.check()`` call must be performed by the calling layer; the
    result is then handed to ``evaluate`` as the *context*.

    Example::

        result = await rate_limiter.check(quota, user_id)
        policy_result = QuotaPolicy().evaluate(result)
        if not policy_result:
            raise QuotaExceededError(policy_result.reason)
    """

    def evaluate(self, context: _RateLimitResult) -> PolicyResult:  # type: ignore[override]
        if context.allowed:
            return PolicyResult.permit(
                f"quota has {context.remaining} request(s) remaining "
                f"(window: {context.quota.window_label})"
            )
        retry = context.retry_after_seconds
        return PolicyResult.deny(
            f"quota exceeded for '{context.quota.key}'; "
            f"retry after {retry:.0f}s (limit: {context.quota.window_label})"
        )


# ---------------------------------------------------------------------------
# Local type alias (avoid circular import — RateLimitResult imported lazily)
# ---------------------------------------------------------------------------

try:
    from mp_commons.application.rate_limit.rate_limiter import (
        RateLimitResult as _RateLimitResult,
    )
except ImportError:  # pragma: no cover  — library not installed in minimal envs
    _RateLimitResult = object  # type: ignore[assignment,misc]


__all__ = [
    "AllOf",
    "AnyOf",
    "ExpiryPolicy",
    "NoneOf",
    "Policy",
    "PolicyResult",
    "QuotaPolicy",
]
