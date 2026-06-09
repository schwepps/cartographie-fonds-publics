"""Offline transform tests for PLF/LFI voted credits (FSC-26).

Drives ``build`` against a tiny PLF "dépenses selon destination" fixture and asserts the FSC-26
contract: one voted ``BudgetFact`` per (exercice, mission, programme) with AE+CP summed at the
**programme grain** (across action rows), ``executed=False``, ``entity_siren=None``, ``0``
preserved, blank amounts -> None, and no row silently dropped.
"""

from __future__ import annotations

from pathlib import Path

from core.models import BudgetFact
from ingestion.tabular import parse_csv_bytes
from ingestion.transforms import TransformResult, get_transform
from ingestion.transforms.budget_common import parse_amount, parse_year
from ingestion.transforms.budget_plf_lfi import SOURCE_ID, build

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _build() -> TransformResult:
    headers, rows = parse_csv_bytes((FIXTURES / "plf_depenses_sample.csv").read_bytes())
    return build(headers, rows)


def _fact(
    result: TransformResult, exercice: int, mission: str | None, programme: str | None
) -> BudgetFact:
    return next(
        f
        for f in result.budget_facts
        if f.exercice == exercice and f.mission == mission and f.programme == programme
    )


def test_emits_one_voted_fact_per_programme() -> None:
    result = _build()
    assert len(result.budget_facts) == 4
    assert all(f.executed is False for f in result.budget_facts)
    assert all(f.entity_siren is None for f in result.budget_facts)


def test_aggregates_actions_to_the_programme_grain() -> None:
    # Programme 150 has two action rows (AE 1_000_000 + 0; CP 900_000 + 500_000) → one summed fact.
    fact = _fact(_build(), 2025, "MIRES", "150")
    assert fact.amount_ae_eur == 1_000_000  # 0 preserved in the sum, not dropped
    assert fact.amount_cp_eur == 1_400_000


def test_other_programmes_carry_their_own_totals() -> None:
    result = _build()
    assert _fact(result, 2025, "MIRES", "172").amount_ae_eur == 2_000_000
    assert _fact(result, 2024, "MIRES", "172").amount_cp_eur == 1_400_000


def test_blank_amounts_become_none_not_zero() -> None:
    fact = _fact(_build(), 2025, "ECOL", None)
    assert fact.amount_ae_eur is None
    assert fact.amount_cp_eur is None


def test_report_accounts_for_every_row() -> None:
    report = _build().report
    assert report["source_id"] == SOURCE_ID
    assert report["rows_in"] == 5
    assert report["facts_out"] == 4
    assert report["dropped_no_exercice"] == 0
    assert report["exercices"] == [2024, 2025]
    assert report["executed"] is False


def test_registered_entry_point_matches_build() -> None:
    headers, rows = parse_csv_bytes((FIXTURES / "plf_depenses_sample.csv").read_bytes())
    assert get_transform(SOURCE_ID)(headers, rows).report == build(headers, rows).report


def test_rows_without_a_usable_exercice_are_dropped_and_counted() -> None:
    # A garbage exercice cell can't form a fact — it must be dropped AND surfaced (golden rule #5),
    # never silently absorbed. Driven inline so the fixture-based counts above stay stable.
    headers = ["Exercice", "Code mission", "Code programme", "AE", "CP"]
    rows = [{"Exercice": "n/a", "Code mission": "X", "Code programme": "1", "AE": "5", "CP": "5"}]
    result = build(headers, rows)
    assert result.budget_facts == []
    assert result.report["dropped_no_exercice"] == 1
    assert result.report["facts_out"] == 0


def test_parse_amount_handles_french_formatting_and_zero() -> None:
    assert parse_amount("1 800 000,50") == 1_800_000.5
    assert parse_amount("0") == 0.0  # a real value — never None
    assert parse_amount("") is None
    assert parse_amount("NaN") is None
    assert parse_amount("inf") is None  # non-finite must not poison a sum
    assert parse_amount("Infinity") is None
    assert parse_year("PLF 2025") == 2025
    assert parse_year("n/a") is None
