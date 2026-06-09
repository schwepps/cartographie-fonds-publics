"""Reviewed, versioned entity crosswalk — the hard-case half of golden rule #5.

When an entity carries no SIREN, resolution falls back to this crosswalk: a name->SIREN map whose
``auto`` rows are reproducible *exact* normalized-name matches and whose ``reviewed`` rows are
human-confirmed. ``pending``/``category`` rows yield no SIREN — they are the curation backlog and
the resolver routes them to the unresolved report, never guessing and never dropping them.

This module is **pure** (no file I/O): the YAML lives in ``data/crosswalk/`` and is loaded by
``ingestion.crosswalk_io``, which builds a :class:`Crosswalk` from in-memory entries. The lookup
key is ``normalize_name(denomination)`` — the same key the resolver computes from an entity name,
so a crosswalk row and the entity it resolves agree by construction.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from pydantic import Field, model_validator

from .models import OptionalSiren, _FrozenModel
from .resolve import normalize_name


class CrosswalkStatus(StrEnum):
    auto = "auto"  # reproducible exact normalized-name match -> SIREN accepted
    reviewed = "reviewed"  # human-confirmed -> SIREN accepted
    pending = "pending"  # needs review, no accepted SIREN (the curation backlog)
    category = "category"  # a category label with no own SIREN, by design


# Statuses whose row yields a SIREN at resolve time. Everything else routes to the report.
_ACCEPTED: frozenset[CrosswalkStatus] = frozenset({CrosswalkStatus.auto, CrosswalkStatus.reviewed})


class CrosswalkEntry(_FrozenModel):
    """One reviewed mapping from an entity name to a SIREN (or to a documented non-match).

    ``normalized_name`` is always recomputed from ``denomination`` so the lookup key stays
    canonical regardless of what a hand-edited file holds — the denomination is the source of
    truth. The status<->SIREN invariant is enforced loud: accepted rows must carry a SIREN;
    backlog rows must not (a ``pending`` row with a SIREN means a reviewer forgot to flip status).
    """

    denomination: str
    status: CrosswalkStatus
    siren: OptionalSiren = None
    normalized_name: str = ""  # derived from denomination on validation; never trusted as input
    tutelle: str | None = None
    candidate_sirens: list[str] = Field(default_factory=list)  # reviewer hints (not validated)
    top_match_ratio: float | None = None  # difflib hint for the backlog (descriptive only)
    source: str | None = None  # provenance: "spike-auto", "manual", ...
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _canonicalize_and_check(self) -> CrosswalkEntry:
        denomination = self.denomination.strip()
        if not denomination:
            raise ValueError("crosswalk entry requires a non-empty denomination")
        self.denomination = denomination
        self.normalized_name = normalize_name(denomination)
        if not self.normalized_name:
            raise ValueError(f"denomination {denomination!r} normalizes to an empty key")
        accepted = self.status in _ACCEPTED
        if accepted and self.siren is None:
            raise ValueError(f"{self.status} entry {denomination!r} must carry a SIREN")
        if not accepted and self.siren is not None:
            raise ValueError(
                f"{self.status} entry {denomination!r} must not carry a SIREN "
                f"(got {self.siren!r}); flip status to 'reviewed' once confirmed"
            )
        return self


class Crosswalk:
    """In-memory name->entry index. Resolves only accepted rows; fails loud on real collisions."""

    def __init__(self, by_name: dict[str, CrosswalkEntry]) -> None:
        self._by_name = by_name

    @classmethod
    def from_entries(cls, entries: Iterable[CrosswalkEntry]) -> Crosswalk:
        """Index entries by their canonical key. Duplicate keys with *different* SIRENs fail loud;
        identical-SIREN duplicates are idempotent (first wins)."""
        by_name: dict[str, CrosswalkEntry] = {}
        for entry in entries:
            existing = by_name.get(entry.normalized_name)
            if existing is not None:
                if existing.siren != entry.siren:
                    raise ValueError(
                        f"crosswalk collision on key {entry.normalized_name!r}: conflicting SIRENs "
                        f"{existing.siren!r} ({existing.denomination!r}) vs {entry.siren!r} "
                        f"({entry.denomination!r}). The normalization key is too coarse for these "
                        "two entities — a reviewer must disambiguate the source names."
                    )
                continue  # idempotent duplicate
            by_name[entry.normalized_name] = entry
        return cls(by_name)

    def resolve(self, normalized_name: str) -> str | None:
        """Return the SIREN for an accepted (auto/reviewed) row, else None."""
        entry = self._by_name.get(normalized_name)
        if entry is not None and entry.status in _ACCEPTED:
            return entry.siren
        return None

    def get(self, normalized_name: str) -> CrosswalkEntry | None:
        return self._by_name.get(normalized_name)

    def entries(self) -> list[CrosswalkEntry]:
        """All entries, sorted by key for stable output."""
        return sorted(self._by_name.values(), key=lambda e: e.normalized_name)

    def __contains__(self, normalized_name: object) -> bool:
        return normalized_name in self._by_name

    def __len__(self) -> int:
        return len(self._by_name)
