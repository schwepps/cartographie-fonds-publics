"""Offline transform tests for the social-protection accounts (DREES dataset 305, FSC-34).

Drives ``build`` against a tiny DREES-shaped fixture (two hierarchies: risque × secteur) and asserts
the FSC-34 contract: aggregated ``social`` budget facts by risque with NO entities/edges (the social
layer is an autonomous module), the consolidated grain guard (top risk level × all-régimes), the
curated risque allowlist, **one fact per (exercice, risque) with no summing** (a duplicate
consolidated row is reported, not added — golden rule #8), millions→euros conversion, ``0``
preserved, and every input row accounted for in the report (golden rule #5).
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


def test_emits_one_aggregated_fact_per_risque_exercice() -> None:
    result = _build()
    # 4 risques in 2022 + Santé 2021 + Logement 2021 = 6 facts.
    assert len(result.budget_facts) == 6
    assert {(f.exercice, f.programme) for f in result.budget_facts} == {
        (2022, "SANTÉ"),
        (2022, "VIEILLESSE-SURVIE"),
        (2022, "FAMILLE"),
        (2022, "EMPLOI"),
        (2021, "SANTÉ"),
        (2021, "LOGEMENT"),
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


def test_grain_guard_excludes_grand_total_subgrains_and_individual_regimes() -> None:
    # The grand total (ps_niveau 0), a prestation sub-level (ps_niveau 2), an individual régime
    # (si_nom != "Total tous régimes") and an off-allowlist risque must NOT appear — keeping any
    # would double-count or pollute the curated set (anti-double-counting, golden rule #8).
    branches = {f.programme for f in _build().budget_facts}
    assert branches == {"SANTÉ", "VIEILLESSE-SURVIE", "FAMILLE", "EMPLOI", "LOGEMENT"}


def test_duplicate_consolidated_rows_reported_not_summed_keyed_on_normalised_label() -> None:
    # A second top-grain row for (2022, Santé) labelled "santé" (casing variant) must be flagged —
    # not added: the figure stays the first consolidated value and the cased variant collapses onto
    # same risque so it spawns no second fact (golden rule #8). Dedup keys on the normalised label.
    result = _build()
    assert result.report["duplicate_grain"] == 1
    sante_2022 = [f for f in result.budget_facts if f.exercice == 2022 and f.programme == "SANTÉ"]
    assert len(sante_2022) == 1  # the "santé" variant did not create a separate fact
    assert sante_2022[0].amount_cp_eur == 315_000_000_000  # 315000 M€ -> €, not 315000+999000


def test_amount_converted_millions_to_euros_and_zero_preserved() -> None:
    facts = _build().budget_facts
    vieillesse_2022 = next(
        f for f in facts if f.exercice == 2022 and f.programme == "VIEILLESSE-SURVIE"
    )
    assert vieillesse_2022.amount_cp_eur == 382_000_000_000  # 382000 millions -> euros
    # `0` is a real figure, never coerced to None/dropped (falsy-safety, golden rule on zero).
    logement_2021 = next(f for f in facts if f.exercice == 2021 and f.programme == "LOGEMENT")
    assert logement_2021.amount_cp_eur == 0


def test_report_accounts_for_every_row_never_silently_dropped() -> None:
    report = _build().report
    assert report["source_id"] == SOURCE_ID
    assert report["rows_in"] == 12
    assert report["facts_out"] == 6
    assert report["skipped_branche"] == 1  # "DIVERS" (off the curated risque allowlist)
    assert report["skipped_subgrain"] == 3  # grand total + prestation sub-level + individual régime
    assert report["dropped_no_exercice"] == 1  # the Emploi row with a blank year
    assert report["dropped_no_amount"] == 0
    assert report["duplicate_grain"] == 1  # the "santé" 2022 consolidated casing variant
    assert report["branches"] == ["EMPLOI", "FAMILLE", "LOGEMENT", "SANTÉ", "VIEILLESSE-SURVIE"]
    assert report["exercices"] == [2021, 2022]
    assert report["resolution_rate"] == 6 / 8  # 6 fact-contributing of 8 in-allowlist-grain rows
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
