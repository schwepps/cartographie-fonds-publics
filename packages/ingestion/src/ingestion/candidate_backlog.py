"""Shared YAML envelope for generated candidate backlogs (FSC-66/67).

Both the attribution (Légifrance) and mention (Cour des comptes) extractors write a human-review
backlog with the same shape: a ``schema_version`` + a ``candidates:`` list, a "do not auto-load"
header, deterministic ordering, and drop-empty-optionals row serialization — never auto-loaded by a
transform. This is the single implementation of that envelope; each feature supplies its field
tuple, header text, dataclass↔row mapping, and sort key, so the validation/header/dump logic can't
drift between the two backlogs.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1


def row_from_fields(obj: object, fields: Sequence[str]) -> dict[str, Any]:
    """Serialize ``obj``'s ``fields`` to a YAML row, dropping genuinely-absent optionals.

    Drops ``None``, empty string and empty list — but never a meaningful ``0``/``0.0`` (e.g. a
    ``match_count`` or ``match_ratio`` of zero must survive the round-trip).
    """
    row: dict[str, Any] = {}
    for fname in fields:
        value = getattr(obj, fname)
        if value is None or (isinstance(value, list) and not value) or value == "":
            continue
        row[fname] = value
    return row


def write_backlog(path: Path | str, *, header: str, rows: Sequence[dict[str, Any]]) -> None:
    """Write a backlog YAML (header + schema_version + candidates); creates parent dirs."""
    doc: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "candidates": list(rows)}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.safe_dump(doc, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)


def read_backlog(path: Path | str) -> list[dict[str, Any]]:
    """Parse a candidate backlog YAML into raw row dicts (validates the envelope; fails loud)."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping, got {type(data).__name__}")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"{path}: unsupported schema_version {data.get('schema_version')!r}, "
            f"expected {SCHEMA_VERSION}"
        )
    rows = data.get("candidates", [])
    if not isinstance(rows, list):
        raise ValueError(f"{path}: 'candidates' must be a list, got {type(rows).__name__}")
    return rows
