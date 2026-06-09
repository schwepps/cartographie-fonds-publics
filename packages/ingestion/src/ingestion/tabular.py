"""Minimal CSV parsing shared by transforms. Production replacement for the spike helpers.

A snapshot extract is raw bytes; a transform needs columns + rows. These two helpers decode and
parse a French-open-data CSV (BOM-tolerant, delimiter-sniffed) and locate a column by pattern —
the same approach proven in ``spikes/phase0_siren_match/spike.py`` but with no dependency on the
spike package.
"""

from __future__ import annotations

import csv
import io
import re


def parse_csv_bytes(raw: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Decode + parse a CSV extract, sniffing the delimiter (French open data favours ';')."""
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:8192]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    return (list(reader.fieldnames or [])), rows


def column_by_name(headers: list[str], pattern: str) -> str | None:
    """First header matching ``pattern`` (case-insensitive), else None."""
    return next((h for h in headers if h and re.search(pattern, h, re.I)), None)


def first_column(headers: list[str], patterns: tuple[str, ...]) -> str | None:
    """First header matching any pattern in priority order (e.g. leaf operator before category)."""
    for pattern in patterns:
        col = column_by_name(headers, pattern)
        if col:
            return col
    return None
