"""Application export – CsvExporter."""
from __future__ import annotations

import csv
import io

from mp_commons.application.export.request import ExportRequest

__all__ = ["CsvExporter"]


class CsvExporter:
    """Streams rows into a CSV file (in-memory)."""

    def __init__(
        self,
        delimiter: str = ",",
        quoting: int = csv.QUOTE_MINIMAL,
        *,
        bom: bool = False,
    ) -> None:
        self._delimiter = delimiter
        self._quoting = quoting
        self._bom = bom

    async def export(self, request: ExportRequest) -> bytes:
        """Return the complete CSV content as bytes (UTF-8, optional BOM)."""
        buf = io.StringIO()
        if self._bom:
            buf.write("\ufeff")  # BOM for Excel compatibility

        writer = csv.writer(buf, delimiter=self._delimiter, quoting=self._quoting)
        writer.writerow([col.header for col in request.columns])

        async for row in request.rows:
            writer.writerow([row.get(col.key, "") for col in request.columns])

        return buf.getvalue().encode("utf-8")
