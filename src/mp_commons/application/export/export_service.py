"""Application export – ExportService dispatches to correct exporter."""
from __future__ import annotations

import json
import time

from mp_commons.application.export.request import ExportRequest
from mp_commons.application.export.csv_export import CsvExporter

__all__ = ["ExportService"]


class ExportService:
    """Dispatches an ExportRequest to the appropriate exporter."""

    def __init__(self, *, bom: bool = False) -> None:
        self._csv_exporter = CsvExporter(bom=bom)

    async def export(self, request: ExportRequest) -> bytes:
        start = time.monotonic()
        result: bytes

        if request.format == "csv":
            result = await self._csv_exporter.export(request)

        elif request.format == "xlsx":
            # Import lazily so missing openpyxl only fails at call time
            from mp_commons.application.export.excel_export import ExcelExporter  # noqa: PLC0415
            result = await ExcelExporter().export(request)

        elif request.format == "json":
            result = await self._export_json(request)

        else:
            raise ValueError(f"Unsupported export format: {request.format!r}")

        duration_ms = (time.monotonic() - start) * 1000  # noqa: F841  # metrics hook point
        return result

    @staticmethod
    async def _export_json(request: ExportRequest) -> bytes:
        rows: list[dict] = []
        async for row in request.rows:
            rows.append({col.key: row.get(col.key) for col in request.columns})
        return json.dumps(rows, default=str, ensure_ascii=False).encode("utf-8")
