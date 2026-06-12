"""Whole-perimeter reconciliation on the **real merged** 4-layer dataset (FSC-58).

Builds the combined curated bundle the same way the FSC-57 pipeline test does — every source in
``ALL_SOURCE_IDS`` snapshotted from its committed fixture, transformed and merged through the real
loader — but **offline** (``build_bundle``, no Postgres), so this always runs in ``pytest`` and the
``python`` CI job, not only the DB job. It then proves the anti-double-counting convention
(``core.methodology`` / ADR-0007) holds on that combined data:

  * the merged budget facts genuinely span **more than one accounting universe**;
  * the per-universe totals **partition** the facts exactly — no euro counted in two universes;
  * within LOLF, **voted and executed are kept separate** (summing them would double-count — the
    residual is *named*, the headline filters to voted, golden rule #8);
  * the delegation hop (contracts) is a **separate accounting object** from the budget universes, so
    a euro at the funding and the delegation hop is never folded into one universe total.

The fixture slice (and its drift guard) is shared with ``test_pipeline_integration.py`` via the
``whole_perimeter_snapshot_root`` conftest fixture, so the offline and DB reconciliations provably
load the *same* coherent cross-source data.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core.methodology import (
    LOLF,
    M57,
    SOCIAL,
    mixes_perimeters,
    perimeter_totals,
    universe_for_level,
    universe_for_nomenclature,
)
from core.models import Level, Nomenclature
from ingestion.load import ALL_SOURCE_IDS, LoadBundle, build_bundle


@pytest.fixture(scope="module")
def bundle(whole_perimeter_snapshot_root: Path) -> LoadBundle:
    """The real merged whole-perimeter bundle, built offline from the shared fixture slice."""
    return build_bundle(ALL_SOURCE_IDS, snapshot_root=whole_perimeter_snapshot_root)


def test_merged_facts_span_more_than_one_universe(bundle: LoadBundle) -> None:
    """The combined load really is cross-universe — State (LOLF), local (M57) and social all
    present, so the reconciliation below is exercised, not vacuous."""
    totals = perimeter_totals(bundle.budget_facts)
    assert {LOLF, M57, SOCIAL} <= set(totals)
    assert set(totals) <= {LOLF, M57, SOCIAL}  # m14 folds into M57; no stray universe


def test_per_universe_totals_partition_the_facts(bundle: LoadBundle) -> None:
    """AC2: the per-universe buckets reconcile to the grand CP sum exactly — every fact lands in
    exactly one universe, none double-counted across universes, none silently dropped."""
    totals = perimeter_totals(bundle.budget_facts)
    grand = sum(f.amount_cp_eur or 0.0 for f in bundle.budget_facts)
    # `approx`: the buckets re-sum the same floats in a different grouping order, and float addition
    # is non-associative — a partition can differ from the single grand reduction by 1 ULP once the
    # fixtures carry fractional amounts (the DB sibling test asserts this invariant the same way).
    assert sum(totals.values()) == pytest.approx(grand)


def test_any_consolidated_total_is_flagged_mixed(bundle: LoadBundle) -> None:
    """A total computed over the merged facts spans universes, so the methodology note is forced —
    a consolidated whole-perimeter figure can never be presented as a plain sum."""
    assert mixes_perimeters([f.nomenclature for f in bundle.budget_facts]) is True


def test_lolf_voted_and_executed_are_kept_separate(bundle: LoadBundle) -> None:
    """AC2 residual *explained, not hidden*: within LOLF the merge carries both voted (PLF) and
    executed (execution) facts. Summing the two bases would double-count the State effort, so the
    convention keeps them distinct (the headline sums voted only); both bases must be present and
    non-zero for that distinction to be real here."""
    lolf = [f for f in bundle.budget_facts if universe_for_nomenclature(f.nomenclature) == LOLF]
    voted = sum(f.amount_cp_eur or 0.0 for f in lolf if not f.executed)
    executed = sum(f.amount_cp_eur or 0.0 for f in lolf if f.executed)
    assert voted > 0.0
    assert executed > 0.0
    assert {f.executed for f in lolf} == {False, True}


def test_delegation_hop_is_separate_from_budget_universes(bundle: LoadBundle) -> None:
    """AC1: the delegation hop (DECP contracts) is a *recipient* layer, not a budget universe
    (``universe_for_level(delegated) is None``). Its money lives in ``bundle.contracts``, never in
    ``budget_facts`` — so a euro counted as a subvention and again as the operator's onward contract
    is never summed into one universe total (it is surfaced, not netted; ADR-0007)."""
    assert universe_for_level(Level.delegated) is None
    assert bundle.contracts, "fixtures should carry DECP contracts (the delegation hop)"
    # Structural disjointness: the per-universe totals are keyed *only* by budget-fact universes
    # (delegated maps to None, so contracts can never create a bucket), and perimeter_totals accepts
    # `Iterable[BudgetFact]` — `bundle.contracts` has no code path into it. So the delegation hop's
    # money is never folded into a universe total, even when its magnitude is large.
    totals = perimeter_totals(bundle.budget_facts)
    assert set(totals) <= {LOLF, M57, SOCIAL}
    assert sum(c.montant_eur or 0.0 for c in bundle.contracts) > 0.0  # the hop is real & non-zero


def test_every_fact_maps_to_a_known_universe(bundle: LoadBundle) -> None:
    """Defensive partition-key check: every merged fact's nomenclature resolves to one of the three
    universes (the bucket key is always present, so no fact escapes the reconciliation)."""
    for fact in bundle.budget_facts:
        assert universe_for_nomenclature(fact.nomenclature) in {LOLF, M57, SOCIAL}
        assert isinstance(fact.nomenclature, Nomenclature)
