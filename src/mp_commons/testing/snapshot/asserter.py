"""Snapshot asserter and store."""

from __future__ import annotations

import difflib
from pathlib import Path

from mp_commons.testing.snapshot.serializer import SnapshotSerializer

__all__ = [
    "SnapshotAsserter",
    "SnapshotStore",
]


class SnapshotStore:
    """Persist and retrieve snapshot files on disk."""

    def __init__(self, directory: str | Path = "tests/__snapshots__") -> None:
        self._dir = Path(directory)

    def _path(self, name: str) -> Path:
        safe = name.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe}.snap"

    def load(self, name: str) -> str | None:
        p = self._path(name)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def save(self, name: str, content: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path(name).write_text(content, encoding="utf-8")

    def exists(self, name: str) -> bool:
        return self._path(name).exists()

    def delete(self, name: str) -> None:
        p = self._path(name)
        if p.exists():
            p.unlink()


class SnapshotAsserter:
    """Assert that a value matches a stored snapshot.

    On first run (snapshot absent) the snapshot is created automatically.
    Pass ``update=True`` to overwrite an existing snapshot.
    """

    def __init__(
        self,
        store: SnapshotStore | None = None,
        serializer: SnapshotSerializer | None = None,
        update: bool = False,
    ) -> None:
        self._store = store or SnapshotStore()
        self._serializer = serializer or SnapshotSerializer()
        self._update = update

    def assert_matches_snapshot(self, value: object, snapshot_name: str) -> None:
        serialised = self._serializer.serialize(value)

        if self._update or not self._store.exists(snapshot_name):
            self._store.save(snapshot_name, serialised)
            return

        stored = self._store.load(snapshot_name)
        if stored == serialised:
            return

        diff = "\n".join(
            difflib.unified_diff(
                stored.splitlines() if stored else [],
                serialised.splitlines(),
                fromfile="snapshot",
                tofile="actual",
                lineterm="",
            )
        )
        raise AssertionError(f"Snapshot mismatch for {snapshot_name!r}:\n{diff}")
