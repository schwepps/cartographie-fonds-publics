"""Offline transform tests for the social-protection accounts (DREES / Urssaf / LFSS, FSC-34).

Drives ``build`` against a tiny DREES-shaped fixture and asserts the FSC-34 contract: aggregated
``social`` budget facts by branche with NO entities/edges (the social layer is an autonomous
module), the curated branche allowlist + consolidated-grain guard, **one fact per (exercice,
branche) with no summing** (a duplicate consolidated row is reported, not added — golden rule #8),
``0`` preserved, and every input row accounted for in the report (golden rule #5).
"""

from __future__ import annotations

from pathlib import Path

from core.models import Nomenclature
from ingestion.tabular import parse_csv_bytes
from ingestion.transforms import TransformResult, get_transform
from ingestion.transforms.comptes_sociaux import SOURCE_ID, build

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _build() -> TransformResult:
    headers, rows = parse_csv_bytes((FIXTURES / "comptes_sociaux_sample.csv").read_bytes())
    return build(headers, rows)


def test_emits_one_aggregated_fact_per_branche_exercice() -> None:
    result = _build()
    # 5 branches in 2022 + Maladie 2021 + Famille 2021 (zero) = 7 facts.
    assert len(result.budget_facts) == 7
    assert {(f.exercice, f.programme) for f in result.budget_facts} == {
        (2021, "Famille"),
        (2021, "Maladie"),
        (2022, "Maladie"),
        (2022, "Vieillesse"),
        (2022, "Famille"),
        (2022, "AT-MP"),
        (2022, "Autonomie"),
    }


def test_facts_are_social_aggregated_with_no_graph_linkage() -> None:
    result = _build()
    facts = result.budget_facts
    assert all(f.nomenclature is Nomenclature.social for f in facts)
    assert all(f.executed is True for f in facts)
    assert all(f.entity_siren is None for f in facts)  # aggregated module: not a SIREN entity
    assert all(f.mission is None and f.amount_ae_eur is None for f in facts)
    # The social layer emits no entities and no edges — it is deliberately not woven into the graph.
    assert result.entities == []
    assert result.edges == []


def test_allowlist_and_grain_exclude_overlapping_total_and_subgrain() -> None:
    # "Ensemble des branches" (sums the branches) and the "Régime agricole" sub-row for Maladie must
    # not appear — keeping either would double-count (anti-double-counting, golden rule #8).
    branches = {f.programme for f in _build().budget_facts}
    assert branches == {"Maladie", "Vieillesse", "Famille", "AT-MP", "Autonomie"}


def test_duplicate_consolidated_row_is_reported_not_summed() -> None:
    # A second top-grain row for (2022, Maladie) — labelled "Ensemble" — must be flagged, not added:
    # the figure stays the first consolidated value, never 240 Md€ + 999 Md€ (golden rule #8).
    result = _build()
    assert result.report["duplicate_grain"] == 1
    maladie_2022 = next(
        f for f in result.budget_facts if f.exercice == 2022 and f.programme == "Maladie"
    )
    assert maladie_2022.amount_cp_eur == 240_000_000_000


def test_amount_parsed_and_zero_preserved() -> None:
    facts = _build().budget_facts
    vieillesse_2022 = next(f for f in facts if f.exercice == 2022 and f.programme == "Vieillesse")
    assert vieillesse_2022.amount_cp_eur == 340_000_000_000  # "340 000 000 000" (space thousands)
    # `0` is a real figure, never coerced to None/dropped (falsy-safety, golden rule on zero).
    famille_2021 = next(f for f in facts if f.exercice == 2021 and f.programme == "Famille")
    assert famille_2021.amount_cp_eur == 0


def test_report_accounts_for_every_row_never_silently_dropped() -> None:
    report = _build().report
    assert report["source_id"] == SOURCE_ID
    assert report["rows_in"] == 11
    assert report["facts_out"] == 7
    assert report["skipped_branche"] == 1  # "Ensemble des branches" (off the curated allowlist)
    assert report["skipped_subgrain"] == 1  # Maladie "Régime agricole" (régime sub-grain)
    assert report["dropped_no_exercice"] == 1  # the Vieillesse row with a blank year
    assert report["dropped_no_amount"] == 0
    assert report["duplicate_grain"] == 1  # the second Maladie 2022 consolidated row
    assert report["branches"] == ["AT-MP", "Autonomie", "Famille", "Maladie", "Vieillesse"]
    assert report["exercices"] == [2021, 2022]
    assert report["resolution_rate"] == 7 / 9  # 7 fact-contributing of 9 in-scope rows
    # Exhaustive: every input row lands in exactly one bucket or a fact (golden rule #5).
    assert (
        report["skipped_branche"]
        + report["skipped_subgrain"]
        + report["dropped_no_exercice"]
        + report["dropped_no_amount"]
        + report["duplicate_grain"]
        + report["facts_out"]
        == report["rows_in"]
    )


def test_registered_entry_point_matches_build() -> None:
    headers, rows = parse_csv_bytes((FIXTURES / "comptes_sociaux_sample.csv").read_bytes())
    assert get_transform(SOURCE_ID)(headers, rows).report == build(headers, rows).report
