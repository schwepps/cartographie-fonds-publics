"""Deterministic Cour des comptes full-text → entity candidate extraction (FSC-67).

The (semi-)automated scaling path for the « contrôle » layer: parse a report PDF to plain text and
scan it for known entity names/acronyms from the reviewed crosswalk + ministry reference, emitting
candidate mentions resolved on SIREN. This is **not** ML/NER — it is a transparent gazetteer
matcher, so it is fully offline-testable and can never fabricate a SIREN (golden rule #5): a hit on
an accepted (SIREN-carrying) entry resolves; a hit on a pending entry, or anything else, is routed
to the review backlog. Precision over recall — a mention is a public-trust signal.

It is **not** a registered transform: it produces *candidates* for human review, not published
``Mention`` rows. The published « contrôle » layer stays the reviewed editorial YAML
(:mod:`ingestion.transforms.cour_des_comptes`). A reviewer promotes a vetted candidate into
``data/mentions/cour_des_comptes.yaml`` (see ``data/mentions/candidates/README.md``); only then does
it render on a fiche.

Recall limit (documented, deliberate): an entity that is *absent* from the crosswalk cannot be
auto-detected here (no NER). Such names surface only through the editorial path. The gazetteer's job
is to scale coverage over entities we already track, with high precision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from core.crosswalk import CrosswalkEntry, CrosswalkStatus
from core.resolve import normalize_name

SOURCE_ID = "cour_des_comptes"
DEFAULT_LICENSE = "Licence Ouverte 2.0"

# Precision guards (documented in data/mentions/candidates/README.md):
# - a denomination surface must carry at least this many distinctive tokens (drops bare "Agence"),
# - an acronym surface must be all-caps and at least this long (drops 1–2 char collisions),
# - matches are word-boundary anchored (so "Agence Alpha" never matches inside "Agence Alphabet").
MIN_SURFACE_TOKENS = 2
MIN_ACRONYM_LEN = 3
_EXCERPT_RADIUS = 120

# Decompression-bomb guards: a small compressed PDF can expand to a huge page count / text volume,
# over which every gazetteer term's regex would then run. Bound both and fail loud (no silent cap).
# Cour des comptes reports are well under these; the caps only trip on pathological/hostile inputs.
MAX_PDF_PAGES = 2000
MAX_TEXT_CHARS = 20_000_000

# All-caps token of >= MIN_ACRONYM_LEN (3) chars: one leading cap + at least two more.
_ACRONYM_RE = re.compile(r"[A-ZÉÈÀÂÎÔÛÇ][A-ZÉÈÀÂÎÔÛÇ0-9&]{2,}")
_SEGMENT_RE = re.compile(r"\s[-–—/]\s")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class GazetteerTerm:
    """One literal surface to scan for, with the entity it identifies."""

    surface: str  # the literal string scanned for in the report text
    normalized: str  # normalize_name(surface) — collision key
    siren: str | None  # resolved SIREN (None → pending entry → backlog, never guessed)
    canonical: str  # the crosswalk entry denomination (candidate identity for dedup)
    kind: str  # "denomination" | "acronym"


@dataclass(frozen=True)
class Gazetteer:
    """Scannable entity surfaces, longest-first so the most specific match wins."""

    terms: list[GazetteerTerm]

    def __len__(self) -> int:
        return len(self.terms)


@dataclass(frozen=True)
class ReportInput:
    """One Cour des comptes report to scan (its PDF + the editorial metadata for the candidate)."""

    url: str
    report_ref: str
    report_date: str | None
    mention_type: str  # "rapport" | "recommandation"
    pdf_bytes: bytes
    license: str | None = None


@dataclass(frozen=True)
class MentionCandidate:
    """One auto-extracted report→entity link awaiting human review (never auto-published)."""

    entity_denomination: str  # the crosswalk entry name
    entity_siren: str | None  # resolved, or None → backlog (never guessed)
    report_ref: str
    report_date: str | None
    mention_type: str
    url: str
    note: str  # excerpt around the first match (reviewer evidence)
    match_count: int  # times the entity was named (precision signal)
    resolution_status: str  # "resolved" | "unresolved"
    provenance: str = SOURCE_ID
    license: str = DEFAULT_LICENSE


@dataclass(frozen=True)
class CandidateResult:
    """Extracted candidates + a coverage/match-rate report (no I/O)."""

    candidates: list[MentionCandidate]
    report: dict[str, Any] = field(default_factory=dict)


def extract_text(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF; fail loud on unreadable/encrypted/empty (no OCR guessing)."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except (PdfReadError, OSError, ValueError) as exc:
        raise ValueError(f"unreadable PDF ({len(pdf_bytes)} bytes): {exc}") from exc
    if reader.is_encrypted:
        raise ValueError("encrypted PDF — cannot extract text (never guess)")
    pages = reader.pages
    if len(pages) > MAX_PDF_PAGES:
        raise ValueError(
            f"PDF has {len(pages)} pages (> {MAX_PDF_PAGES} cap) — refusing (bomb guard)"
        )
    parts: list[str] = []
    total = 0
    for page in pages:
        chunk = page.extract_text() or ""
        total += len(chunk)
        if total > MAX_TEXT_CHARS:
            raise ValueError(
                f"extracted text exceeded {MAX_TEXT_CHARS} chars — refusing (bomb guard)"
            )
        parts.append(chunk)
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError(
            "PDF yielded no extractable text (scanned/image PDF?) — fail loud, no OCR guessing"
        )
    return text


def _surfaces(denomination: str) -> list[tuple[str, str]]:
    """Scannable ``(surface, kind)`` forms of a denomination: each dash segment + its acronym."""
    out: list[tuple[str, str]] = []
    for segment in _SEGMENT_RE.split(denomination):
        segment = segment.strip()
        if not segment:
            continue
        if _ACRONYM_RE.fullmatch(segment):
            out.append((segment, "acronym"))
        elif len(normalize_name(segment).split()) >= MIN_SURFACE_TOKENS:
            out.append((segment, "denomination"))
    return out


def build_gazetteer(
    crosswalk_entries: list[CrosswalkEntry],
    ministry_entries: list[CrosswalkEntry],
) -> Gazetteer:
    """Build the scannable gazetteer from reviewed entities, dropping ambiguous surfaces.

    Includes accepted operators (resolve to their SIREN), ``pending`` operators (siren=None → a
    backlog candidate) and ministries. ``category`` grouping labels are excluded (not real
    entities). Each entry contributes surfaces from its ``denomination`` **and** its curated
    ``aliases`` (former names / common acronyms, FSC-70) — both run through the same precision
    guards, so an alias is just another exact-match surface, never a fuzzy match. A surface that
    normalizes to two different SIRENs is dropped — never guess.
    """
    # value None marks a surface dropped as ambiguous (seen with two different SIRENs).
    by_norm: dict[str, GazetteerTerm | None] = {}

    def _add(entry: CrosswalkEntry) -> None:
        # Scan the denomination plus every curated alias; the canonical identity stays the
        # denomination so dedup + the candidate's entity name are unchanged by an alias hit.
        for source_name in (entry.denomination, *entry.aliases):
            for surface, kind in _surfaces(source_name):
                normalized = normalize_name(surface)
                if not normalized:
                    continue
                if normalized not in by_norm:
                    by_norm[normalized] = GazetteerTerm(
                        surface=surface,
                        normalized=normalized,
                        siren=entry.siren,
                        canonical=entry.denomination,
                        kind=kind,
                    )
                    continue
                existing = by_norm[normalized]
                if existing is not None and existing.siren != entry.siren:
                    # Same surface, two different entities → ambiguous; drop it (never guess).
                    by_norm[normalized] = None

    for entry in crosswalk_entries:
        if entry.status is CrosswalkStatus.category:
            continue
        _add(entry)
    for entry in ministry_entries:
        _add(entry)

    terms = [t for t in by_norm.values() if t is not None]
    # Longest surface first so the most specific match is preferred and excerpts are anchored well.
    terms.sort(key=lambda t: len(t.surface), reverse=True)
    return Gazetteer(terms=terms)


def link_entities(
    text: str, gazetteer: Gazetteer, *, report: ReportInput
) -> list[MentionCandidate]:
    """Scan ``text`` for gazetteer surfaces (word-boundary), one candidate per distinct entity."""
    by_canonical: dict[str, MentionCandidate] = {}
    for term in gazetteer.terms:
        # Acronyms are matched case-sensitively (the precision guard): "CNRS" must not hit "cnrs".
        # Full denominations stay case-insensitive (sentence-case in prose is expected).
        flags = 0 if term.kind == "acronym" else re.IGNORECASE
        pattern = re.compile(rf"(?<!\w){re.escape(term.surface)}(?!\w)", flags)
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        existing = by_canonical.get(term.canonical)
        count = (existing.match_count if existing else 0) + len(matches)
        note = existing.note if existing else _excerpt(text, matches[0].start(), matches[0].end())
        by_canonical[term.canonical] = MentionCandidate(
            entity_denomination=term.canonical,
            entity_siren=term.siren,
            report_ref=report.report_ref,
            report_date=report.report_date,
            mention_type=report.mention_type,
            url=report.url,
            note=note,
            match_count=count,
            resolution_status="resolved" if term.siren else "unresolved",
            license=report.license or DEFAULT_LICENSE,
        )
    return list(by_canonical.values())


def _excerpt(text: str, start: int, end: int) -> str:
    """A trimmed ±radius window around a match — the reviewer's evidence snippet."""
    left = max(0, start - _EXCERPT_RADIUS)
    right = min(len(text), end + _EXCERPT_RADIUS)
    snippet = _WS_RE.sub(" ", text[left:right]).strip()
    return f"…{snippet}…" if (left > 0 or right < len(text)) else snippet


def build_candidates(
    reports: list[ReportInput],
    *,
    crosswalk_entries: list[CrosswalkEntry],
    ministry_entries: list[CrosswalkEntry],
) -> CandidateResult:
    """Extract+link every report; report coverage (reports with a hit) and match rate (resolved)."""
    gazetteer = build_gazetteer(crosswalk_entries, ministry_entries)
    candidates: list[MentionCandidate] = []
    reports_with_hit = 0
    for report in reports:
        text = extract_text(report.pdf_bytes)
        found = link_entities(text, gazetteer, report=report)
        if found:
            reports_with_hit += 1
        candidates.extend(found)

    total = len(candidates)
    resolved = sum(1 for c in candidates if c.resolution_status == "resolved")
    report_dict: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "gazetteer_terms": len(gazetteer),
        "reports_total": len(reports),
        "reports_with_candidates": reports_with_hit,
        "coverage_rate": (reports_with_hit / len(reports)) if reports else None,
        "candidates_total": total,
        "candidates_resolved": resolved,
        "match_rate": (resolved / total) if total else None,
        "unresolved_candidates": [
            {"entity_denomination": c.entity_denomination, "report_ref": c.report_ref}
            for c in candidates
            if c.resolution_status == "unresolved"
        ],
    }
    return CandidateResult(candidates=candidates, report=report_dict)
