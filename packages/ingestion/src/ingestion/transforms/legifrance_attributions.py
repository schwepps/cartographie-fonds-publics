"""Transform editorial ministerial attributions into ``Attribution`` rows (FSC-27, manual-first).

The "why" layer: décrets d'attribution that mandate ministries. **Manual/editorial-first** — a
curated YAML (``data/attributions/ministres.yaml``) of *real* décrets, each resolved to its
ministry's SIREN through the reviewed ministry reference (``ministeres.yaml``), never guessed. An
entry that does not resolve is surfaced in the report, never attached to a guessed SIREN (golden
rule #5).

The live PISTE/Légifrance extraction + text→entity NLP is the **documented scaling path** (FSC-66),
deliberately not run here: this is the lowest-priority Phase-1 layer and must stay lean. The
``rest`` connector (``connectors/rest.py``) registers for the registry source's ``platform: rest``
and documents that path; this transform is the offline, editorial source of truth for the
demonstrable attributions.

It is pure: persistence is the loader's job (FSC-35). The registered entry point loads the committed
editorial file + ministry reference; :func:`build` takes them as arguments for offline tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from core.models import Attribution

from . import TransformResult, register_transform
from .operateurs_etat import MinistryIndex

SOURCE_ID = "legifrance_attributions"
SCHEMA_VERSION = 1

# Committed editorial file (same default-path + CFP_* env-override convention as crosswalk_io).
_DEFAULT_ATTRIBUTIONS_PATH = (
    Path(__file__).resolve().parents[5] / "data" / "attributions" / "ministres.yaml"
)
ATTRIBUTIONS_PATH = Path(os.environ.get("CFP_ATTRIBUTIONS_PATH", _DEFAULT_ATTRIBUTIONS_PATH))


@dataclass(frozen=True)
class AttributionEntry:
    """One editorial attribution row: a décret d'attribution targeting a ministry.

    The ministry is referenced by its ``tutelle`` code (the key ``ministeres.yaml`` resolves) or,
    failing that, its ``denomination`` — never a SIREN (resolved at build time, golden rule #1/#5).
    """

    legal_ref: str
    source_url: str
    txt: str
    tutelle: str | None = None
    denomination: str | None = None


def load_attribution_entries(path: Path | str = ATTRIBUTIONS_PATH) -> list[AttributionEntry]:
    """Parse the committed editorial attributions YAML (fails loud on a malformed file/row)."""
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
    entries: list[AttributionEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{path}: each entry must be a mapping, got {type(row).__name__}")
        legal_ref = str(row.get("legal_ref") or "").strip()
        source_url = str(row.get("source_url") or "").strip()
        txt = str(row.get("txt") or "").strip()
        tutelle = str(row.get("tutelle") or "").strip() or None
        denomination = str(row.get("denomination") or "").strip() or None
        if not legal_ref or not source_url:
            raise ValueError(
                f"{path}: every attribution needs a non-empty 'legal_ref' + 'source_url'"
            )
        if not source_url.lower().startswith(("http://", "https://")):
            raise ValueError(f"{path}: source_url must be an http(s) URL, got {source_url!r}")
        if not (tutelle or denomination):
            raise ValueError(
                f"{path}: attribution {legal_ref!r} needs a 'tutelle' code or a 'denomination'"
            )
        entries.append(
            AttributionEntry(
                legal_ref=legal_ref,
                source_url=source_url,
                txt=txt,
                tutelle=tutelle,
                denomination=denomination,
            )
        )
    return entries


def build(entries: list[AttributionEntry], *, ministries: MinistryIndex) -> TransformResult:
    """Pure transform: editorial entries -> ``Attribution`` rows resolved on the ministry SIREN."""
    attributions: list[Attribution] = []
    unresolved: list[dict[str, str | None]] = []
    for entry in entries:
        ministry = ministries.resolve(entry.tutelle or entry.denomination)
        if ministry is None or ministry.siren is None:
            unresolved.append(
                {
                    "legal_ref": entry.legal_ref,
                    "tutelle": entry.tutelle,
                    "denomination": entry.denomination,
                }
            )
            continue
        attributions.append(
            Attribution(
                entity_siren=ministry.siren,
                legal_ref=entry.legal_ref,
                txt=entry.txt or None,
                source_url=entry.source_url,
                provenance=SOURCE_ID,
            )
        )
    report: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "total": len(entries),
        "attributions": len(attributions),
        "unresolved": len(unresolved),
        "unresolved_entries": unresolved,
    }
    return TransformResult(attributions=attributions, report=report)


@register_transform(SOURCE_ID)
def transform(_headers: list[str], _rows: list[dict[str, str]]) -> TransformResult:
    """Registered entry point. Editorial-first: reads the committed YAML, not the snapshot rows.

    The ``rest`` connector still discovers/snapshots upstream (proving the source resolves), but the
    curated mandates come from the reviewed editorial file — the live PISTE extraction is the
    documented scaling path (FSC-66), so the snapshot rows are intentionally not consumed here.
    """
    return build(load_attribution_entries(), ministries=MinistryIndex.load())
