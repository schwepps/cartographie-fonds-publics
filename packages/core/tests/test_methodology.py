"""Tests for the anti-double-counting perimeter mapping (FSC-42) + reconciliation (FSC-58)."""

from __future__ import annotations

from core.methodology import (
    LOLF,
    M57,
    SOCIAL,
    mixes_perimeters,
    perimeter_totals,
    universe_for_level,
    universe_for_nomenclature,
)
from core.models import BudgetFact, Edge, EdgeType, Level, Nomenclature


def test_nomenclature_maps_to_universe() -> None:
    assert universe_for_nomenclature(Nomenclature.lolf) == LOLF
    assert universe_for_nomenclature(Nomenclature.m57) == M57
    assert universe_for_nomenclature(Nomenclature.m14) == M57  # M14 + M57 = same local universe
    assert universe_for_nomenclature(Nomenclature.social) == SOCIAL


def test_level_maps_to_universe_delegated_is_none() -> None:
    assert universe_for_level(Level.state) == LOLF
    assert universe_for_level(Level.local) == M57
    assert universe_for_level(Level.social) == SOCIAL
    assert universe_for_level(Level.delegated) is None  # a recipient, not a budget universe


def test_single_universe_is_not_mixed() -> None:
    assert mixes_perimeters([Nomenclature.lolf, Nomenclature.lolf]) is False
    assert mixes_perimeters([Nomenclature.m57, Nomenclature.m14]) is False  # same local universe
    assert mixes_perimeters([Level.state, Level.state]) is False


def test_crossing_universes_is_mixed() -> None:
    assert mixes_perimeters([Nomenclature.lolf, Nomenclature.m57]) is True
    assert mixes_perimeters([Level.state, Level.local]) is True
    assert mixes_perimeters([Nomenclature.lolf, Level.local]) is True  # mixed key types allowed


def test_delegated_alone_does_not_make_a_mix() -> None:
    assert mixes_perimeters([Level.state, Level.delegated]) is False
    assert mixes_perimeters([Level.delegated, Level.delegated]) is False


# --- Reconciliation: perimeter_totals partitions facts by universe (FSC-58) ------------------

# A combined fact set spanning all four nomenclatures. Two LOLF rows (voted + executed) show that
# perimeter_totals sums *within* a universe; an m57 + m14 pair shows they fold into one local
# universe; a None-amount and a 0.0-amount row guard the falsy/None handling (0 is a real value).
# (nomenclature, amount_cp_eur, executed)
_FACT_ROWS: list[tuple[Nomenclature, float | None, bool]] = [
    (Nomenclature.lolf, 100.0, False),  # voted State credits
    (Nomenclature.lolf, 20.0, True),  # executed State credits — same universe, also summed
    (Nomenclature.m57, 50.0, True),
    (Nomenclature.m14, 5.0, True),  # folds into the M57 local universe
    (Nomenclature.social, 200.0, True),
    (Nomenclature.lolf, None, False),  # unknown amount (≠ 0) contributes nothing
    (Nomenclature.m57, 0.0, True),  # a real 0.0 is preserved, not dropped
]


def _combined_facts() -> list[BudgetFact]:
    return [
        BudgetFact(
            entity_siren=None, exercice=2025, amount_cp_eur=cp, executed=executed, nomenclature=nom
        )
        for nom, cp, executed in _FACT_ROWS
    ]


def test_perimeter_totals_buckets_by_universe() -> None:
    totals = perimeter_totals(_combined_facts())
    # LOLF sums both voted (100) + executed (20); None contributes nothing. M57 = m57 (50) + m14 (5)
    # + a real 0.0 (preserved, not dropped). SOCIAL = 200. m14 has no key of its own.
    assert totals == {LOLF: 120.0, M57: 55.0, SOCIAL: 200.0}
    assert set(totals) <= {LOLF, M57, SOCIAL}


def test_perimeter_totals_partition_is_exact() -> None:
    """The per-universe buckets partition the facts: their sum equals the grand CP sum, with every
    fact in exactly one universe — so no euro is ever counted in two universes (ADR-0007)."""
    facts = _combined_facts()
    grand = sum(f.amount_cp_eur or 0.0 for f in facts)
    assert sum(perimeter_totals(facts).values()) == grand


def test_combined_facts_force_the_methodology_note() -> None:
    """A total computed over the combined set spans >1 universe, so any consolidated figure must
    carry the methodology note rather than be read as a sum."""
    assert mixes_perimeters([f.nomenclature for f in _combined_facts()]) is True


def test_transfer_edges_never_enter_a_universe_total() -> None:
    """AC1: a State→local subvention is an `edges` row, not a `budget_facts` row — so it can never
    double-count into the State (LOLF) or local (M57) budget total. perimeter_totals consumes facts
    only; the transfer edge below has no path into the per-universe sums."""
    facts = _combined_facts()
    transfer = Edge(
        source_siren="110044013",  # a State ministry
        target_siren="217500016",  # a local collectivité
        type=EdgeType.funds,
        amount_eur=999_000.0,
        exercice=2025,
    )
    totals = perimeter_totals(facts)
    # Both endpoints' universe totals are exactly their own facts — the coexisting 999_000 transfer
    # inflates neither the local (M57 = 50 + 5 + 0) nor the State (LOLF = 100 + 20) budget total. A
    # flow is not a fact; perimeter_totals sums BudgetFacts only, so the Edge never enters a bucket.
    assert totals[M57] == 55.0
    assert totals[LOLF] == 120.0
    assert transfer.amount_eur not in totals.values()
