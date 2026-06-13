"""Transform the Cour des comptes editorial mapping into ``Mention`` rows (FSC-62, metadata-first).

The registry ``cour_des_comptes`` source is discovered + snapshotted by the existing
``datagouv_api`` connector (proving the no-hardcoded-slug discovery AC), but the upstream corpus is
PDF + thin
metadata with **no structured entity field** (verified: the org's only recommendations dataset is a
2015–2018 plain-text file, ODbL). So the report→entity link is supplied by a reviewed editorial
mapping (``data/mentions/cour_des_comptes.yaml``) for the demonstrable subset, resolved to a SIREN
through the crosswalk + ministry reference — unresolved rows are reported, never guessed (golden
rule #5).

Full-text NLP linking (PDF → entity) is the **documented scaling path** (FSC-67), explicitly out of
scope here, matching the ticket's "metadata-first" coverage promise.

Pure: persistence is the loader's job. The registered entry point loads the committed mapping +
crosswalk + ministry reference; :func:`build` takes them as arguments for offline tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from core.crosswalk import Crosswalk
from core.models import Mention, MentionType
from core.resolve import normalize_name

from ..crosswalk_io import load_crosswalk
from . import TransformResult, register_transform
from .operateurs_etat import MinistryIndex

SOURCE_ID = "cour_des_comptes"
SCHEMA_VERSION = 1
# Default per-row licence. The audit corpus is not uniformly licensed; an entry may override it
# (e.g. the published-recommendations dataset is ODbL, not Licence Ouverte). Stored per ``Mention``.
DEFAULT_LICENSE = "Licence Ouverte 2.0"

# Committed editorial mapping (same default-path + CFP_* env-override convention as crosswalk_io).
_DEFAULT_MENTIONS_PATH = (
    Path(__file__).resolve().parents[5] / "data" / "mentions" / "cour_des_comptes.yaml"
)
MENTIONS_PATH = Path(os.environ.get("CFP_MENTIONS_PATH", _DEFAULT_MENTIONS_PATH))


@dataclass(frozen=True)
class MentionEntry:
    """One editorial mention row: a Cour des comptes publication concerning an entity.

    The entity is referenced by ``entity_denomination`` (an operator name resolved via the
    crosswalk, or a ministry name/code via the ministry reference) — never a SIREN.
    """

    entity_denomination: str
    report_ref: str
    report_date: str
    mention_type: MentionType
    url: str
    note: str | None = None
    license: str | None = None


def load_mention_entries(path: Path | str = MENTIONS_PATH) -> list[MentionEntry]:
    """Parse the committed editorial mentions YAML (fails loud on a malformed file/row)."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping, got {type(data).__name__}")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"{path}: unsupported schema_version {data.get('schema_version')!r}, "
            f"expected {SCHEMA_VERSION}"
        )
    rows = data.get("entries", [])
    if not isinstance(rows, list):
        raise ValueError(f"{path}: 'entries' must be a list, got {type(rows).__name__}")
    entries: list[MentionEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{path}: each entry must be a mapping, got {type(row).__name__}")
        denomination = str(row.get("entity_denomination") or "").strip()
        report_ref = str(row.get("report_ref") or "").strip()
        report_date = str(row.get("report_date") or "").strip()
        url = str(row.get("url") or "").strip()
        raw_type = str(row.get("mention_type") or "").strip()
        note = str(row.get("note") or "").strip() or None
        license_ = str(row.get("license") or "").strip() or None
        if not denomination or not report_ref or not url:
            raise ValueError(
                f"{path}: every mention needs 'entity_denomination' + 'report_ref' + 'url'"
            )
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError(f"{path}: url must be an http(s) URL, got {url!r}")
        try:
            mention_type = MentionType(raw_type)
        except ValueError as exc:
            allowed = ", ".join(t.value for t in MentionType)
            raise ValueError(
                f"{path}: mention_type {raw_type!r} for {report_ref!r} must be one of {allowed}"
            ) from exc
        entries.append(
            MentionEntry(
                entity_denomination=denomination,
                report_ref=report_ref,
                report_date=report_date,
                mention_type=mention_type,
                url=url,
                note=note,
                license=license_,
            )
        )
    return entries


def _resolve_siren(
    denomination: str, crosswalk: Crosswalk, ministries: MinistryIndex
) -> str | None:
    """Resolve an entity name to a SIREN: operator crosswalk first, then the ministry reference."""
    siren = crosswalk.resolve(normalize_name(denomination))
    if siren is not None:
        return siren
    ministry = ministries.resolve(denomination)
    return ministry.siren if ministry is not None else None


def build(
    entries: list[MentionEntry],
    *,
    crosswalk: Crosswalk,
    ministries: MinistryIndex,
) -> TransformResult:
    """Pure transform: editorial mention entries -> ``Mention`` rows resolved on entity SIREN."""
    mentions: list[Mention] = []
    unresolved: list[dict[str, str]] = []
    for entry in entries:
        siren = _resolve_siren(entry.entity_denomination, crosswalk, ministries)
        if siren is None:
            unresolved.append(
                {"entity_denomination": entry.entity_denomination, "report_ref": entry.report_ref}
            )
            continue
        mentions.append(
            Mention(
                entity_siren=siren,
                report_ref=entry.report_ref,
                report_date=entry.report_date or None,
                mention_type=entry.mention_type,
                url=entry.url,
                note=entry.note,
                provenance=SOURCE_ID,
                license=entry.license or DEFAULT_LICENSE,
            )
        )
    resolved = len(mentions)
    total = len(entries)
    report: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "total": total,
        "mentions": resolved,
        "unresolved": len(unresolved),
        "unresolved_entries": unresolved,
        "resolution_rate": (resolved / total) if total else None,
    }
    return TransformResult(mentions=mentions, report=report)


@register_transform(SOURCE_ID)
def transform(_headers: list[str], _rows: list[dict[str, str]]) -> TransformResult:
    """Registered entry point. Metadata-first: reads the committed editorial mapping.

    The ``datagouv_api`` connector discovers/snapshots the upstream dataset (no hardcoded slug), but
    the report→entity link is the reviewed mapping — full-text NLP is the scaling path (FSC-67), so
    the snapshot rows are intentionally not parsed here.
    """
    return build(
        load_mention_entries(),
        crosswalk=load_crosswalk(),
        ministries=MinistryIndex.load(),
    )
