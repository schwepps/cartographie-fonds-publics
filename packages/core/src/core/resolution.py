"""Entity resolution: reconcile on SIREN, route the rest to the crosswalk — never drop, never guess.

The single entry point :func:`resolve_entities` takes the domain entities and the reviewed
:class:`~core.crosswalk.Crosswalk` and returns a :class:`ResolutionResult` that accounts for
*every* input — an entity either keeps/gains a SIREN (``resolved``) or becomes an
:class:`UnresolvedLink` with a documented reason (``unresolved``). The invariant
``len(resolved) + len(unresolved) == len(inputs)`` is the machine form of golden rule #5.

This module is pure: it produces a JSON-serializable, timestamp-free report dict; writing it (and
stamping a run time) is the I/O layer's job (``ingestion.cli resolve``).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from pydantic import Field

from .crosswalk import Crosswalk, CrosswalkStatus
from .models import Entity, FrozenModel
from .resolve import normalize_name


class UnresolvedReason(StrEnum):
    no_siren_no_crosswalk = "no_siren_no_crosswalk"  # no own SIREN and no crosswalk row at all
    pending_review = "pending_review"  # a backlog row awaiting human confirmation
    multiple_candidates = "multiple_candidates"  # ambiguous: several candidate SIRENs, none chosen
    category_label = "category_label"  # a category label with no own SIREN, by design


class UnresolvedLink(FrozenModel):
    """An entity that could not be reconciled to a SIREN — surfaced, never silently dropped."""

    denomination: str
    normalized_name: str
    reason: UnresolvedReason
    candidate_sirens: list[str] = Field(default_factory=list)
    top_match_ratio: float | None = None


class ResolutionResult(FrozenModel):
    """The full account of a resolution run. ``resolved`` + ``unresolved`` cover every input."""

    resolved: list[Entity] = Field(default_factory=list)
    unresolved: list[UnresolvedLink] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.resolved) + len(self.unresolved)

    @property
    def resolution_rate(self) -> float:
        """Share of entities carrying a SIREN after resolution. Distinct from
        ``core.resolve.match_rate`` (cross-source set overlap). Zero-guarded at total==0."""
        return len(self.resolved) / self.total if self.total else 0.0

    def reason_counts(self) -> dict[str, int]:
        counts = {reason.value: 0 for reason in UnresolvedReason}
        for link in self.unresolved:
            counts[link.reason.value] += 1
        return counts

    def to_report_dict(self) -> dict[str, Any]:
        """Deterministic, timestamp-free report (criterion: 'unresolved links' report each run)."""
        return {
            "total": self.total,
            "resolved": len(self.resolved),
            "unresolved": len(self.unresolved),
            "resolution_rate": round(self.resolution_rate, 4),
            "unresolved_by_reason": self.reason_counts(),
            "unresolved_links": [
                link.model_dump()
                for link in sorted(self.unresolved, key=lambda link_: link_.normalized_name)
            ],
        }


def _unresolved(entity: Entity, key: str, crosswalk: Crosswalk) -> UnresolvedLink:
    """Classify why an unresolved entity stayed unresolved, carrying any reviewer hints."""
    entry = crosswalk.get(key)
    if entry is None:
        reason = UnresolvedReason.no_siren_no_crosswalk
        candidates: list[str] = []
        ratio: float | None = None
    else:
        candidates, ratio = entry.candidate_sirens, entry.top_match_ratio
        if entry.status is CrosswalkStatus.category:
            reason = UnresolvedReason.category_label
        elif len(entry.candidate_sirens) > 1:
            reason = UnresolvedReason.multiple_candidates
        else:
            reason = UnresolvedReason.pending_review
    return UnresolvedLink(
        denomination=entity.name,
        normalized_name=key,
        reason=reason,
        candidate_sirens=candidates,
        top_match_ratio=ratio,
    )


def resolve_entities(entities: Iterable[Entity], crosswalk: Crosswalk) -> ResolutionResult:
    """Reconcile each entity on SIREN. Keep entities that already carry one; fill the rest from the
    crosswalk; route the still-unresolved to the report. Output preserves every input (no drops)."""
    resolved: list[Entity] = []
    unresolved: list[UnresolvedLink] = []
    for entity in entities:
        if entity.siren is not None:
            resolved.append(entity)
            continue
        key = normalize_name(entity.name)
        siren = crosswalk.resolve(key)
        if siren is not None:
            resolved.append(entity.model_copy(update={"siren": siren}))
        else:
            unresolved.append(_unresolved(entity, key, crosswalk))
    return ResolutionResult(resolved=resolved, unresolved=unresolved)
