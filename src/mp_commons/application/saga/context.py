"""Application saga – SagaContext."""

from __future__ import annotations

from typing import Any


class SagaContext:
    """Shared mutable state passed through each step of a saga.

    Steps read and write arbitrary keys.  An immutable snapshot can be
    obtained via :meth:`snapshot` for durable persistence.
    """

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(initial or {})

    # ------------------------------------------------------------------
    # dict-like access
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any) -> None:  # noqa: ANN401
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:  # noqa: ANN401
        return self._data.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"SagaContext({self._data!r})"

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a shallow copy of the current context data."""
        return dict(self._data)

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "SagaContext":
        """Restore a context from a previously taken snapshot."""
        return cls(data)


__all__ = ["SagaContext"]
