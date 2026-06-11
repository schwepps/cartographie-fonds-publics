"""Offline transform tests for OFGL local-authority finances (FSC-32).

Drives ``build`` against a tiny OFGL agrégat fixture and asserts the FSC-32 contract: local entities
+ ``m57`` budget facts on the collectivité SIREN, the curated expenditure agrégat allowlist (so
overlapping rows like "Dépenses totales"/"Recettes …" are excluded to avoid double-counting), 0
preserved, and unresolved SIRENs reported (golden rule #5), never silently dropped.
"""

from __future__ import annotations

from pathlib import Path

from core.models import Level, Nomenclature
from ingestion.tabular import parse_csv_bytes
from ingestion.transforms import TransformResult, get_transform
from ingestion.transforms.finances_locales_ofgl import SOURCE_ID, build

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _build() -> TransformResult:
    headers, rows = parse_csv_bytes((FIXTURES / "ofgl_sample.csv").read_bytes())
    return build(headers, rows)


def test_emits_local_entities_per_collectivite() -> None:
    result = _build()
    assert len(result.entities) == 2  # Lyon + Paris (the no-SIREN row yields no entity)
    assert all(e.level is Level.local for e in result.entities)
    assert {e.siren for e in result.entities} == {"216901231", "217500016"}
    lyon = next(e for e in result.entities if e.siren == "216901231")
    assert lyon.name == "Lyon"
    assert lyon.category == "Commune de 100 000 hab et plus"


def test_budget_facts_are_m57_executed_on_the_collectivite() -> None:
    facts = _build().budget_facts
    # Lyon (fonct. + invest.) + Paris (2023 fonct. + 2022 fonct. + 2023 invest.) = 5 facts.
    assert len(facts) == 5
    assert all(f.nomenclature is Nomenclature.m57 for f in facts)
    assert all(f.executed is True for f in facts)
    assert all(f.mission is None and f.amount_ae_eur is None for f in facts)
    assert all(f.entity_siren is not None for f in facts)


def test_curated_allowlist_excludes_overlapping_agregats() -> None:
    # "Dépenses totales" and "Recettes de fonctionnement" must not appear — summing them with the
    # expenditure pair would double-count (anti-double-counting, golden rule #8).
    programmes = {f.programme for f in _build().budget_facts}
    assert programmes == {"Dépenses de fonctionnement", "Dépenses d'investissement"}


def test_amounts_parsed_from_french_formatting() -> None:
    facts = _build().budget_facts
    lyon_fonct = next(
        f
        for f in facts
        if f.entity_siren == "216901231" and f.programme == "Dépenses de fonctionnement"
    )
    assert lyon_fonct.amount_cp_eur == 1_200_000_000  # "1 200 000 000" (NBSP/space thousands)
    assert lyon_fonct.exercice == 2023


def test_unresolved_siren_is_reported_not_dropped_silently() -> None:
    report = _build().report
    assert report["source_id"] == SOURCE_ID
    assert report["unresolved_siren"] == 1  # the no-SIREN "Dépenses de fonctionnement" row
    assert report["skipped_agregat"] == 2  # "Dépenses totales" + "Recettes de fonctionnement"
    assert report["facts_out"] == 5
    assert report["entities_out"] == 2
    assert report["exercices"] == [2022, 2023]
    assert report["resolution_rate"] == 5 / 6  # 5 resolved of 6 allowlisted rows


def test_registered_entry_point_matches_build() -> None:
    headers, rows = parse_csv_bytes((FIXTURES / "ofgl_sample.csv").read_bytes())
    assert get_transform(SOURCE_ID)(headers, rows).report == build(headers, rows).report
