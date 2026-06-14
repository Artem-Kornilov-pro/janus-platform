"""Pure helpers for exporting tabular data to CSV.

Kept free of any Qt imports so the export logic can be unit tested without a
display.
"""

from __future__ import annotations

import csv
import io


def rows_to_csv(columns: list[str], rows: list[list[str]]) -> str:
    """Render a table (header + rows) as CSV text."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    writer.writerows(rows)
    return buffer.getvalue()
