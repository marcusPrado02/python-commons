"""Unit tests for §66 Application — Data Export."""
from __future__ import annotations

import asyncio

import csv
import io
import json
from typing import AsyncIterator

import pytest

from mp_commons.application.export import ColumnDef, CsvExporter, ExportRequest, ExportService


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def _rows(*dicts) -> AsyncIterator[dict]:
    for d in dicts:
        yield d


# ---------------------------------------------------------------------------
# ColumnDef
# ---------------------------------------------------------------------------
class TestColumnDef:
    def test_basic(self):
        col = ColumnDef(key="name", header="Full Name")
        assert col.key == "name"
        assert col.header == "Full Name"
        assert col.format == ""

    def test_with_format(self):
        col = ColumnDef(key="created_at", header="Created", format="date")
        assert col.format == "date"


# ---------------------------------------------------------------------------
# CsvExporter
# ---------------------------------------------------------------------------
class TestCsvExporter:
    def test_produces_headers(self):
        async def _run():
            exporter = CsvExporter()
            req = ExportRequest(
                columns=[ColumnDef("id", "ID"), ColumnDef("name", "Name")],
                rows=_rows(),
                format="csv",
            )
            data = await exporter.export(req)
            text = data.decode("utf-8")
            first_line = text.splitlines()[0]
            assert first_line == "ID,Name"
        asyncio.run(_run())
    def test_produces_data_rows(self):
        async def _run():
            exporter = CsvExporter()
            req = ExportRequest(
                columns=[ColumnDef("id", "ID"), ColumnDef("name", "Name")],
                rows=_rows({"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}),
                format="csv",
            )
            data = await exporter.export(req)
            reader = csv.reader(io.StringIO(data.decode("utf-8")))
            rows = list(reader)
            assert rows[0] == ["ID", "Name"]
            assert rows[1] == ["1", "Alice"]
            assert rows[2] == ["2", "Bob"]
        asyncio.run(_run())
    def test_missing_key_produces_empty_cell(self):
        async def _run():
            exporter = CsvExporter()
            req = ExportRequest(
                columns=[ColumnDef("id", "ID"), ColumnDef("missing", "Ghost")],
                rows=_rows({"id": 42}),
                format="csv",
            )
            data = await exporter.export(req)
            reader = csv.reader(io.StringIO(data.decode("utf-8")))
            rows = list(reader)
            assert rows[1] == ["42", ""]
        asyncio.run(_run())
    def test_bom_prefix(self):
        async def _run():
            exporter = CsvExporter(bom=True)
            req = ExportRequest(
                columns=[ColumnDef("x", "X")],
                rows=_rows(),
                format="csv",
            )
            data = await exporter.export(req)
            assert data.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
        asyncio.run(_run())
    def test_custom_delimiter(self):
        async def _run():
            exporter = CsvExporter(delimiter=";")
            req = ExportRequest(
                columns=[ColumnDef("a", "A"), ColumnDef("b", "B")],
                rows=_rows({"a": "1", "b": "2"}),
                format="csv",
            )
            data = await exporter.export(req)
            lines = data.decode("utf-8").splitlines()
            assert lines[0] == "A;B"
            assert lines[1] == "1;2"
        asyncio.run(_run())
    def test_empty_rows(self):
        async def _run():
            exporter = CsvExporter()
            req = ExportRequest(
                columns=[ColumnDef("id", "ID")],
                rows=_rows(),
                format="csv",
            )
            data = await exporter.export(req)
            lines = [l for l in data.decode("utf-8").splitlines() if l]
            assert lines == ["ID"]
        asyncio.run(_run())
# ---------------------------------------------------------------------------
# ExportService
# ---------------------------------------------------------------------------
class TestExportService:
    def test_csv_format(self):
        async def _run():
            svc = ExportService()
            req = ExportRequest(
                columns=[ColumnDef("name", "Name")],
                rows=_rows({"name": "Alice"}),
                format="csv",
            )
            data = await svc.export(req)
            assert b"Name" in data
            assert b"Alice" in data
        asyncio.run(_run())
    def test_json_format(self):
        async def _run():
            svc = ExportService()
            req = ExportRequest(
                columns=[ColumnDef("id", "id"), ColumnDef("name", "name")],
                rows=_rows({"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}),
                format="json",
            )
            data = await svc.export(req)
            parsed = json.loads(data)
            assert isinstance(parsed, list)
            assert len(parsed) == 2
            assert parsed[0] == {"id": 1, "name": "Alice"}
        asyncio.run(_run())
    def test_unknown_format_raises_value_error(self):
        async def _run():
            svc = ExportService()
            req = ExportRequest(
                columns=[ColumnDef("x", "X")],
                rows=_rows(),
                format="pdf",  # type: ignore[arg-type]
            )
            with pytest.raises(ValueError, match="pdf"):
                await svc.export(req)
        asyncio.run(_run())
    def test_json_empty_rows(self):
        async def _run():
            svc = ExportService()
            req = ExportRequest(
                columns=[ColumnDef("id", "id")],
                rows=_rows(),
                format="json",
            )
            data = await svc.export(req)
            assert json.loads(data) == []
        asyncio.run(_run())
