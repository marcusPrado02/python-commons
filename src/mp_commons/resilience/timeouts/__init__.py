"""Resilience – timeout policies and deadlines."""
from mp_commons.resilience.timeouts.policy import TimeoutPolicy
from mp_commons.resilience.timeouts.deadline import Deadline

__all__ = ["Deadline", "TimeoutPolicy"]
