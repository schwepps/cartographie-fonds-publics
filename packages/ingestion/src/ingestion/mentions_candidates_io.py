"""Read/write the Cour des comptes mention candidate backlog (FSC-67).

The backlog is the human-review queue produced by ``transforms.cour_des_comptes_extract``. It is
**never auto-loaded** by a transform — a reviewer promotes a vetted row into the reviewed
``data/mentions/cour_des_comptes.yaml`` (see ``data/mentions/candidates/README.md``). Same
default-path + ``CFP_*`` env-override convention as ``crosswalk_io``; deterministic ordering for
byte-stable diffs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .transforms.cour_des_comptes_extract import (
    DEFAULT_LICENSE,
    SOURCE_ID,
    CandidateResult,
    MentionCandidate,
)

SCHEMA_VERSION = 1

_DEFAULT_CANDIDATES_PATH = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "mentions"
    / "candidates"
    / "cour_des_comptes_candidates.yaml"
)
CANDIDATES_PATH = Path(os.environ.get("CFP_MENTION_CANDIDATES_PATH", _DEFAULT_CANDIDATES_PATH))

_HEADER = (
    "# DO NOT auto-load. Generated report→entity mention CANDIDATES for human review (FSC-67).\n"
    "# Verify a `resolved` candidate against its url (does the report really épingle it?), then\n"
    "# copy entity_denomination/report_ref/report_date/mention_type/url/note into\n"
    "# data/mentions/cour_des_comptes.yaml. `unresolved` rows need the entity resolved in the\n"
    "# crosswalk first. See data/mentions/candidates/README.md for the promotion process.\n"
)

_CANDIDATE_FIELDS = (
    "entity_denomination",
    "entity_siren",
    "report_ref",
    "report_date",
    "mention_type",
    "url",
    "note",
    "match_count",
    "resolution_status",
    "provenance",
    "license",
)


def _candidate_to_row(candidate: MentionCandidate) -> dict[str, Any]:
    """Serialize a candidate to a YAML row, dropping genuinely-absent optionals for a clean diff."""
    row: dict[str, Any] = {}
    for fname in _CANDIDATE_FIELDS:
        value = getattr(candidate, fname)
        if value is None or value == "":
            continue
        row[fname] = value
    return row


def write_candidates(result: CandidateResult, path: Path | str = CANDIDATES_PATH) -> None:
    """Write the candidate backlog as YAML (stable order), with a 'do not auto-load' header."""
    ordered = sorted(
        result.candidates, key=lambda c: (c.resolution_status, c.report_ref, c.entity_denomination)
    )
    doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "candidates": [_candidate_to_row(c) for c in ordered],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_HEADER)
        yaml.safe_dump(doc, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)


def load_candidates(path: Path | str = CANDIDATES_PATH) -> list[MentionCandidate]:
    """Parse a candidate backlog YAML back into candidates (round-trips ``write_candidates``)."""
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
    out: list[MentionCandidate] = []
    for row in rows:
        out.append(
            MentionCandidate(
                entity_denomination=str(row.get("entity_denomination") or ""),
                entity_siren=row.get("entity_siren"),
                report_ref=str(row.get("report_ref") or ""),
                report_date=row.get("report_date"),
                mention_type=str(row.get("mention_type") or ""),
                url=str(row.get("url") or ""),
                note=str(row.get("note") or ""),
                match_count=int(row.get("match_count") or 0),
                resolution_status=str(row.get("resolution_status") or "unresolved"),
                provenance=str(row.get("provenance") or SOURCE_ID),
                license=str(row.get("license") or DEFAULT_LICENSE),
            )
        )
    return out
