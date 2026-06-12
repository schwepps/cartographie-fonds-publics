"""Assisted curation of the operator crosswalk (FSC-56): promote `pending` rows to `reviewed`.

The spike (`make spike-resolve-live`) auto-resolves ~⅔ of operators by *exact* normalized-name
equality and routes the rest to the `pending` backlog. This module curates that backlog **without
guessing** (golden rule #5): it re-queries the public recherche-entreprises API per pending operator
and accepts a SIREN only when a **single, unambiguous, public-sector** candidate matches by a
*sourced* signal — exact name, the candidate's own `sigle` (acronym), or full name-containment.
Anything ambiguous (several public matches it can't separate) or unmatched stays `pending`, with the
candidate SIRENs recorded as reviewer hints.

Every accepted row becomes a `reviewed` entry whose `notes` carry the API basis (legal name + nature
juridique + the matching signal), so the SIREN is auditable back to its source. `reviewed` rows are
preserved across re-seeds by `crosswalk_io.merge_seed`, so curation is never clobbered.

Pure + offline-testable: the network call is injected as a ``search`` function; the CLI wires the
real httpx client + the registry-driven base URL (never hardcoded).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.crosswalk import CrosswalkEntry, CrosswalkStatus
from core.resolve import normalize_name, normalize_siren

# A recherche-entreprises lookup: an operator name -> candidate result dicts (possibly empty).
SearchFn = Callable[[str], list[dict[str, Any]]]

# Jaune entries are often "ACRONYM - Full legal name"; SIRENE stores the full name (and often the
# acronym in `sigle`). Spaces required around the dash so hyphenated names ("Météo-France") are kept
# whole. Mirrors the spike's variant rule — same artifact, same fix, no fuzzy guessing.
_ACRONYM_PREFIX = re.compile(r"^(?P<acro>[0-9A-Za-zÀ-ÿ&.'’]{2,15})\s+[-–—]\s+(?P<rest>.+\S)$")

# A bare leading acronym token (all-caps, ≥2 chars) when the name has no "ACRONYM - " prefix.
_BARE_ACRONYM = re.compile(r"^(?P<acro>[A-ZÀ-Þ][A-ZÀ-Þ0-9&]{1,14})\b")

# INSEE catégorie juridique 4xxx (EPIC…) / 7xxx (État, EPA/EPST, collectivités) are the public-law
# forms. Used only to disambiguate equally-named candidates — never to accept a non-matching name.
_PUBLIC_NATURE_PREFIXES = ("4", "7")


def _name_variants(denomination: str) -> list[str]:
    """The operator name plus its acronym-stripped form when it carries an 'ACRONYM - ' prefix."""
    variants = [denomination]
    match = _ACRONYM_PREFIX.match(denomination.strip())
    if match:
        variants.append(match.group("rest"))
    return variants


def _acronym(denomination: str) -> str | None:
    """The operator's acronym: the 'ACRONYM - …' prefix, else a bare leading all-caps token."""
    stripped = denomination.strip()
    prefix = _ACRONYM_PREFIX.match(stripped)
    if prefix:
        return prefix.group("acro")
    bare = _BARE_ACRONYM.match(stripped)
    return bare.group("acro") if bare else None


def _tokens(name: str | None) -> frozenset[str]:
    """Significant comparison tokens for a name (accent/case-folded, articles + legal forms out)."""
    return frozenset(normalize_name(name or "").split())


def _candidate_names(candidate: dict[str, Any]) -> list[str]:
    return [n for n in (candidate.get("nom_complet"), candidate.get("nom_raison_sociale")) if n]


def _is_public(candidate: dict[str, Any]) -> bool:
    """Public signal: an administration flag, or a public-law nature juridique (4xxx/7xxx)."""
    comp = candidate.get("complements") or {}
    if comp.get("est_administration") is True:
        return True
    return str(candidate.get("nature_juridique") or "")[:1] in _PUBLIC_NATURE_PREFIXES


def _match_signal(
    variant_tokens: list[frozenset[str]], acronym: str | None, candidate: dict[str, Any]
) -> str | None:
    """Return the sourced match signal for a *public* candidate, else ``None``.

    Order = strength: ``exact`` normalized-name equality, then ``sigle`` (the candidate's own
    acronym equals the operator's), then ``containment`` (the candidate's name contains every
    significant token of an operator-name variant — needs ≥2 tokens, so a single generic word can
    never carry a match). Conservative by design: a wrong SIREN is worse than an unresolved one.
    """
    if not _is_public(candidate):
        return None
    cand_token_sets = [_tokens(n) for n in _candidate_names(candidate)]
    for vt in variant_tokens:
        if vt and any(vt == ct for ct in cand_token_sets):
            return "exact"
    sigle = normalize_name(candidate.get("sigle") or "")
    if acronym and sigle and normalize_name(acronym) == sigle:
        return "sigle"
    cand_tokens = frozenset().union(*cand_token_sets) if cand_token_sets else frozenset()
    for vt in variant_tokens:
        if len(vt) >= 2 and vt <= cand_tokens:
            return "containment"
    return None


@dataclass(frozen=True)
class Proposal:
    """The curation outcome for one pending operator."""

    denomination: str
    accepted: bool
    siren: str | None = None
    signal: str | None = None  # exact | sigle | containment
    note: str | None = None
    candidate_sirens: list[str] = field(default_factory=list)  # public matches when not unique


def propose(entry: CrosswalkEntry, search: SearchFn) -> Proposal:
    """Resolve one pending operator: accept a SIREN only on a single unambiguous public match."""
    variants = _name_variants(entry.denomination)
    variant_tokens = [_tokens(v) for v in variants]
    acronym = _acronym(entry.denomination)

    matched: dict[str, tuple[str, dict[str, Any]]] = {}
    for candidate in search(entry.denomination):
        siren = normalize_siren(candidate.get("siren"))
        if siren is None:
            continue
        signal = _match_signal(variant_tokens, acronym, candidate)
        if signal is not None:
            matched.setdefault(siren, (signal, candidate))

    if len(matched) != 1:
        return Proposal(entry.denomination, accepted=False, candidate_sirens=sorted(matched))

    siren, (signal, candidate) = next(iter(matched.items()))
    sigle = candidate.get("sigle")
    note = (
        f"recherche-entreprises «{candidate.get('nom_complet')}» "
        f"(nature {candidate.get('nature_juridique')}"
        f"{f', sigle {sigle}' if sigle else ''}) — {signal}-match"
    )
    return Proposal(entry.denomination, accepted=True, siren=siren, signal=signal, note=note)


def to_reviewed(
    entry: CrosswalkEntry, proposal: Proposal, *, reviewed_by: str, reviewed_at: str
) -> CrosswalkEntry:
    """Build the `reviewed` entry for an accepted proposal, carrying the API basis in ``notes``."""
    if not (proposal.accepted and proposal.siren):
        raise ValueError(f"cannot review {entry.denomination!r}: proposal was not accepted")
    return CrosswalkEntry(
        denomination=entry.denomination,
        status=CrosswalkStatus.reviewed,
        siren=proposal.siren,
        tutelle=entry.tutelle,
        source="api-curated",
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        notes=proposal.note,
    )


@dataclass(frozen=True)
class CurationResult:
    """The curated entry set + a JSON-serializable report (counts, never row dumps)."""

    entries: list[CrosswalkEntry]
    report: dict[str, Any]


def curate(
    entries: list[CrosswalkEntry], search: SearchFn, *, reviewed_by: str, reviewed_at: str
) -> CurationResult:
    """Curate every `pending` row: accepted ones become `reviewed`; the rest are kept untouched.

    Non-pending rows (auto/reviewed/category) pass through unchanged — re-running is safe and never
    downgrades a human-reviewed row. The report tallies what moved and what stayed in the backlog.
    """
    out: list[CrosswalkEntry] = []
    promoted = 0
    pending_seen = 0
    still_pending: list[str] = []
    for entry in entries:
        if entry.status is not CrosswalkStatus.pending:
            out.append(entry)
            continue
        pending_seen += 1
        proposal = propose(entry, search)
        if proposal.accepted:
            out.append(
                to_reviewed(entry, proposal, reviewed_by=reviewed_by, reviewed_at=reviewed_at)
            )
            promoted += 1
        else:
            out.append(entry)
            still_pending.append(entry.denomination)

    report = {
        "pending_in": pending_seen,
        "promoted_to_reviewed": promoted,
        "still_pending": len(still_pending),
        "still_pending_names": sorted(still_pending),
    }
    return CurationResult(entries=out, report=report)
