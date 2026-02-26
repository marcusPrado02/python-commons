"""Unit tests for §83 – Observability Profiling."""
import pytest

from mp_commons.observability.profiling import (
    CpuSampler,
    MemoryProfiler,
    MemoryStat,
    ProfileReport,
)


class TestMemoryProfiler:
    def test_snapshot_returns_stats(self):
        profiler = MemoryProfiler(top_n=5)
        # Allocate a little to ensure tracemalloc has something
        _ = [bytearray(1024) for _ in range(10)]
        stats = profiler.snapshot()
        assert isinstance(stats, list)
        # May or may not have stats depending on what's traced
        for s in stats:
            assert isinstance(s, MemoryStat)
            assert s.size_bytes >= 0

    def test_snapshot_respects_top_n(self):
        profiler = MemoryProfiler(top_n=3)
        _ = [bytearray(512)] * 5
        stats = profiler.snapshot()
        assert len(stats) <= 3


class TestProfileReport:
    def test_save_writes_file(self, tmp_path):
        report = ProfileReport(duration_ms=50.0, text="profile data", html="<html/>")
        path = tmp_path / "report.html"
        report.save(str(path))
        assert path.read_text() == "<html/>"

    def test_save_uses_text_when_no_html(self, tmp_path):
        report = ProfileReport(duration_ms=10.0, text="text output")
        path = tmp_path / "report.txt"
        report.save(str(path))
        assert path.read_text() == "text output"


class TestCpuSamplerMissingDep:
    def test_start_raises_without_pyinstrument(self):
        sampler = CpuSampler()
        with pytest.raises(ImportError, match="pyinstrument"):
            sampler.start()

    def test_report_before_stop_raises(self):
        sampler = CpuSampler()
        with pytest.raises(RuntimeError):
            sampler.report()
