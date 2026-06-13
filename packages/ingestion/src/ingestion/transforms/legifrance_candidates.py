"""Deterministic, editorial-assisted text→entity linking for décrets d'attribution (FSC-66).

The (semi-)automated scaling path for the « pourquoi » layer: given décrets discovered + fetched by
the PISTE/Légifrance ``rest`` connector, link each one to a ministry by matching its title against
the reviewed ministry reference (``data/crosswalk/ministeres.yaml``). This is **not** an ML/NER
pipeline — it is a transparent token matcher, so it is fully offline-testable and can never
fabricate a SIREN (golden rule #5): a décret resolves only when exactly one ministry's distinctive
tokens are all present in the title; anything ambiguous or unknown is routed to the review backlog.

It is **not** a registered transform: it produces *candidates* for human review, not published
``Attribution`` rows. The published « pourquoi » layer stays the reviewed editorial YAML
(:mod:`ingestion.transforms.legifrance_attributions`). A reviewer promotes a vetted candidate into
``data/attributions/ministres.yaml`` (see ``data/attributions/README.md``); only then does it render
on a fiche. Precision over recall — the legal mandate is a public-trust signal.
"""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from core.crosswalk import CrosswalkEntry
from core.resolve import normalize_name

SOURCE_ID = "legifrance_attributions"
SCHEMA_VERSION = 1
DEFAULT_LICENSE = "Licence Ouverte 2.0"

# Backlog file: generated candidates awaiting human review. Same default-path + CFP_* env-override
# convention as the other data files. NEVER loaded by a transform — promotion is a manual step.
_DEFAULT_CANDIDATES_PATH = (
    Path(__file__).resolve().parents[5]
    / "data"
    / "attributions"
    / "candidates"
    / "ministres_candidates.yaml"
)
CANDIDATES_PATH = Path(os.environ.get("CFP_ATTRIBUTION_CANDIDATES_PATH", _DEFAULT_CANDIDATES_PATH))

# Procedural / generic ministerial tokens dropped before matching, so a décret title reduces to the
# *distinctive* ministry tokens (e.g. "attributions du ministre de la culture" → {culture}).
# normalize_name already strips articles + bare legal forms; this drops the rest.
_GENERIC_TOKENS: frozenset[str] = frozenset(
    {
        "ministre",
        "ministres",
        "ministere",
        "secretaire",
        "secretariat",
        "etat",
        "aupres",
        "charge",
        "chargee",
        "delegue",
        "deleguee",
        "gouvernement",
        "attribution",
        "attributions",
        "decret",
        "relatif",
        "relative",
        "premier",
        "portant",
    }
)

# The minister-naming clause starts at "attributions d…" ("du"/"de la"/"de l'"/"des").
_ATTRIB_RE = re.compile(r"attributions?\s+d", re.IGNORECASE)

# Maximum excerpt kept as reviewer evidence on each candidate.
_EXCERPT_CHARS = 280


@dataclass(frozen=True)
class AttributionCandidate:
    """One auto-extracted décret→ministry link awaiting human review (never auto-published)."""

    legal_ref: str  # the décret title
    source_url: str  # Légifrance permalink
    txt: str  # excerpt around the mandate (reviewer evidence)
    status: str  # "matched" | "unresolved"
    matched_tutelle: str | None = None  # ministry code, when uniquely resolved
    entity_siren: str | None = None  # resolver hint (never published as-is — promotion re-resolves)
    denomination: str | None = None  # ministry name, when uniquely resolved
    candidate_sirens: list[str] = field(default_factory=list)  # hints when ambiguous
    match_ratio: float = 0.0  # difflib confidence of the best ministry match (reviewer hint)
    license: str = DEFAULT_LICENSE  # provenance: per-row licence (golden rule #10)
    provenance: str = SOURCE_ID


@dataclass(frozen=True)
class AttributionCandidateResult:
    """Extracted candidates + a coverage/match-rate report (no I/O)."""

    candidates: list[AttributionCandidate]
    report: dict[str, Any]


def _significant_tokens(text: str) -> frozenset[str]:
    """Distinctive tokens of a name: normalized, minus generic ministerial/procedural words."""
    return frozenset(
        t for t in normalize_name(text).split() if t not in _GENERIC_TOKENS and len(t) > 1
    )


def _minister_phrase(title: str) -> str:
    """The minister clause of a décret title (from the last 'attributions d…'), else the title."""
    matches = list(_ATTRIB_RE.finditer(title))
    return title[matches[-1].start() :] if matches else title


def _denomination_ratio(norm_phrase: str, denomination: str) -> float:
    """difflib confidence between a normalized décret clause and a ministry denomination (hint)."""
    return difflib.SequenceMatcher(None, norm_phrase, normalize_name(denomination)).ratio()


def extract_attribution_candidates(
    decrees: list[dict[str, Any]],
    *,
    ministries: list[CrosswalkEntry],
) -> AttributionCandidateResult:
    """Link each décret to a ministry by title-token containment; route the rest to the backlog.

    A décret resolves only when **exactly one** ministry's distinctive tokens are all contained in
    the title clause (precision over recall). Zero or several matches → ``unresolved`` (candidate
    SIRENs recorded as reviewer hints, never a guessed pick). Every input yields a candidate — none
    is dropped (golden rule #5).
    """
    ministry_tokens = [(m, _significant_tokens(m.denomination)) for m in ministries]
    candidates: list[AttributionCandidate] = []
    matched = 0
    unresolved_entries: list[dict[str, str | None]] = []

    for decree in decrees:
        title = str(decree.get("title") or "").strip()
        url = str(decree.get("url") or "").strip()
        content = str(decree.get("content") or "").strip()
        phrase = _minister_phrase(title)
        decree_tokens = _significant_tokens(phrase)
        excerpt = (content or phrase)[:_EXCERPT_CHARS]

        hits = [m for m, toks in ministry_tokens if toks and toks <= decree_tokens]
        norm_phrase = normalize_name(phrase)

        if len(hits) == 1:
            entry = hits[0]
            matched += 1
            candidates.append(
                AttributionCandidate(
                    legal_ref=title,
                    source_url=url,
                    txt=excerpt,
                    status="matched",
                    matched_tutelle=entry.tutelle,
                    entity_siren=entry.siren,
                    denomination=entry.denomination,
                    match_ratio=round(_denomination_ratio(norm_phrase, entry.denomination), 4),
                )
            )
        else:
            best = max(
                (_denomination_ratio(norm_phrase, m.denomination) for m, _ in ministry_tokens),
                default=0.0,
            )
            candidates.append(
                AttributionCandidate(
                    legal_ref=title,
                    source_url=url,
                    txt=excerpt,
                    status="unresolved",
                    candidate_sirens=[m.siren for m in hits if m.siren],
                    match_ratio=round(best, 4),
                )
            )
            unresolved_entries.append(
                {"legal_ref": title, "reason": "ambiguous" if hits else "no_ministry_match"}
            )

    total = len(candidates)
    report: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "total": total,
        "matched": matched,
        "unresolved": total - matched,
        "match_rate": (matched / total) if total else None,
        "unresolved_entries": unresolved_entries,
    }
    return AttributionCandidateResult(candidates=candidates, report=report)


_HEADER = (
    "# DO NOT auto-load. Generated décret→ministry CANDIDATES for human review (FSC-66).\n"
    "# Verify a `matched` candidate against its source_url, then copy tutelle/legal_ref/\n"
    "# source_url/txt into data/attributions/ministres.yaml (the SIREN is re-resolved at build\n"
    "# time, never carried over). `unresolved` rows first need their ministry in ministeres.yaml.\n"
    "# See data/attributions/README.md for the promotion process.\n"
)

_CANDIDATE_FIELDS = (
    "legal_ref",
    "source_url",
    "status",
    "matched_tutelle",
    "entity_siren",
    "denomination",
    "candidate_sirens",
    "match_ratio",
    "txt",
    "license",
    "provenance",
)


def _candidate_to_row(candidate: AttributionCandidate) -> dict[str, Any]:
    """Serialize a candidate to a YAML row, dropping genuinely-absent optionals for a clean diff."""
    row: dict[str, Any] = {}
    for fname in _CANDIDATE_FIELDS:
        value = getattr(candidate, fname)
        if value is None or (isinstance(value, list) and not value) or value == "":
            continue
        row[fname] = value
    return row


def write_candidates(
    result: AttributionCandidateResult, path: Path | str = CANDIDATES_PATH
) -> None:
    """Write the candidate backlog as YAML (stable order), with a 'do not auto-load' header."""
    ordered = sorted(result.candidates, key=lambda c: (c.status, c.legal_ref))
    doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "candidates": [_candidate_to_row(c) for c in ordered],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_HEADER)
        yaml.safe_dump(doc, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)


def load_candidates(path: Path | str = CANDIDATES_PATH) -> list[AttributionCandidate]:
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
    out: list[AttributionCandidate] = []
    for row in rows:
        out.append(
            AttributionCandidate(
                legal_ref=str(row.get("legal_ref") or ""),
                source_url=str(row.get("source_url") or ""),
                txt=str(row.get("txt") or ""),
                status=str(row.get("status") or "unresolved"),
                matched_tutelle=row.get("matched_tutelle"),
                entity_siren=row.get("entity_siren"),
                denomination=row.get("denomination"),
                candidate_sirens=list(row.get("candidate_sirens") or []),
                match_ratio=float(row.get("match_ratio") or 0.0),
                license=str(row.get("license") or DEFAULT_LICENSE),
                provenance=str(row.get("provenance") or SOURCE_ID),
            )
        )
    return out
