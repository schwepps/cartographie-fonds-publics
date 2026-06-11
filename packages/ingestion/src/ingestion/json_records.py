"""Unwrap and tabularise a JSON extract so the CSV validate/snapshot path can consume it (FSC-47).

ODS Explore wraps its records under ``results``; data.gouv API wrappers use ``data``/``records``.
The envelope key is declared per source in the registry (``records_path``, read via
``registry.Source.records_path``) so nothing about the envelope shape is frozen in code (golden
rule #2). A top-level array needs no key (``record_path=None``).

The records are then rendered to CSV bytes and validated/snapshotted through the **same** proven
path as a CSV extract: frictionless enforces a Table Schema's labels and types on delimited text
(not on keyed JSON), and snapshots are stored ``all_varchar`` — so collapsing records to CSV gives
JSON the identical fail-loud-on-drift + faithful-bytes guarantees, with one code path to maintain.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

JsonRecord = dict[str, Any]


def unwrap_records(raw: bytes, *, record_path: str | None) -> list[JsonRecord]:
    """Parse ``raw`` JSON and return its array of record objects.

    ``record_path`` (when set) is the single top-level envelope key holding the array (e.g.
    ``results``). Fails loud (``ValueError``) on unparseable JSON, an absent key, or a non-array
    value — a malformed envelope is drift, never silently an empty extract.
    """
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"extract is not valid JSON: {exc}") from exc

    if record_path is None:
        records = parsed
    elif not isinstance(parsed, dict):
        raise ValueError(
            f"records_path {record_path!r} is set but the JSON root is "
            f"{type(parsed).__name__}, not an object carrying that key."
        )
    elif record_path not in parsed:
        raise ValueError(
            f"records_path {record_path!r} not found in JSON envelope (keys: {sorted(parsed)})."
        )
    else:
        records = parsed[record_path]

    if not isinstance(records, list):
        where = f" at {record_path!r}" if record_path else ""
        raise ValueError(f"expected a JSON array of records{where}, got {type(records).__name__}.")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("JSON records must be objects (an array of {field: value} records).")
    return records


def records_to_csv_bytes(records: list[JsonRecord]) -> bytes:
    """Render record objects to UTF-8 CSV bytes with a stable, union-of-keys header.

    Column order is first-seen across the records, so a field absent from *every* record drops out
    of the header (surfacing as column drift against the schema), while a field missing on *some*
    rows yields empty cells (a per-cell warning) — matching the CSV drift-vs-warning policy. Nested
    values are JSON-encoded; ``None`` becomes an empty cell (mirrors the ``all_varchar`` read-back).
    """
    fieldnames: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for record in records:
        writer.writerow({key: _cell(record.get(key)) for key in fieldnames})
    return buffer.getvalue().encode("utf-8")


def json_to_csv_bytes(raw: bytes, *, record_path: str | None) -> bytes:
    """Unwrap a JSON extract and render its records to the CSV (tabular) view used downstream."""
    return records_to_csv_bytes(unwrap_records(raw, record_path=record_path))


def _cell(value: Any) -> str:
    """Coerce a JSON scalar to its faithful text form; nested containers are JSON-encoded."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)
