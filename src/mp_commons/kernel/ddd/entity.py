"""Entity base class — identity-based equality."""

from __future__ import annotations

from mp_commons.kernel.types.ids import EntityId


class Entity:
    """Base entity – equality is identity-based (by ``id``)."""

    def __init__(self, id: EntityId) -> None:  # noqa: A002
        self._id = id

    @property
    def id(self) -> EntityId:
        return self._id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:  # pragma: no cover
        return f"{type(self).__name__}(id={self._id!r})"


__all__ = ["Entity"]
