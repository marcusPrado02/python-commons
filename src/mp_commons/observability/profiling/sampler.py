from __future__ import annotations

import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "CpuSampler",
    "MemoryProfiler",
    "MemoryStat",
    "ProfileReport",
]


@dataclass
class ProfileReport:
    duration_ms: float = 0.0
    html: str = ""
    text: str = ""

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.html or self.text, encoding="utf-8")


@dataclass(frozen=True)
class MemoryStat:
    filename: str
    lineno: int
    size_bytes: int
    count: int


def _require_pyinstrument() -> Any:
    try:
        import pyinstrument
        return pyinstrument
    except ImportError:
        raise ImportError(
            "pyinstrument is required for CPU profiling. "
            "Install it with: pip install mp-commons[profiling]"
        ) from None


class CpuSampler:
    """Thin wrapper around pyinstrument.Profiler (optional dep)."""

    def __init__(self) -> None:
        self._profiler: Any = None
        self._report: ProfileReport | None = None

    def start(self) -> None:
        pi = _require_pyinstrument()
        self._profiler = pi.Profiler()
        self._profiler.start()

    def stop(self) -> None:
        if self._profiler is None:
            raise RuntimeError("Profiler not started")
        self._profiler.stop()
        session = self._profiler.last_session
        duration_ms = (session.duration if session else 0) * 1000
        self._report = ProfileReport(
            duration_ms=duration_ms,
            html=self._profiler.output_html(),
            text=self._profiler.output_text(),
        )

    def report(self) -> ProfileReport:
        if self._report is None:
            raise RuntimeError("Call stop() before report()")
        return self._report


class MemoryProfiler:
    """Wraps tracemalloc to capture top-N memory allocations."""

    def __init__(self, top_n: int = 10) -> None:
        self._top_n = top_n

    def snapshot(self) -> list[MemoryStat]:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        snap = tracemalloc.take_snapshot()
        stats = snap.statistics("lineno")
        result: list[MemoryStat] = []
        for s in stats[: self._top_n]:
            frame = s.traceback[0]
            result.append(
                MemoryStat(
                    filename=frame.filename,
                    lineno=frame.lineno,
                    size_bytes=s.size,
                    count=s.count,
                )
            )
        return result
