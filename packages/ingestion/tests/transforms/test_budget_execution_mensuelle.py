"""Offline transform tests for monthly execution (FSC-26).

Drives ``build`` against a tiny "situation mensuelle" fixture and asserts the FSC-26 contract: one
executed ``BudgetFact`` per (exercice, mission, programme) keeping the **latest month only** (months
are cumulative YTD — never summed), ``executed=True``, dépenses -> ``amount_cp_eur``, no AE column
-> ``amount_ae_eur`` None, ``entity_siren=None``, and no row silently dropped.
"""

from __future__ import annotations

from pathlib import Path

from core.models import BudgetFact
from ingestion.tabular import parse_csv_bytes
from ingestion.transforms import TransformResult, get_transform
from ingestion.transforms.budget_execution_mensuelle import SOURCE_ID, _period_key, build

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _build() -> TransformResult:
    headers, rows = parse_csv_bytes((FIXTURES / "ods_situation_mensuelle.csv").read_bytes())
    return build(headers, rows)


def _fact(
    result: TransformResult, exercice: int, mission: str | None, programme: str | None
) -> BudgetFact:
    return next(
        f
        for f in result.budget_facts
        if f.exercice == exercice and f.mission == mission and f.programme == programme
    )


def test_emits_one_executed_fact_per_programme() -> None:
    result = _build()
    assert len(result.budget_facts) == 3
    assert all(f.executed is True for f in result.budget_facts)
    assert all(f.entity_siren is None for f in result.budget_facts)
    assert all(f.amount_ae_eur is None for f in result.budget_facts)  # no AE column in execution


def test_keeps_latest_month_never_sums() -> None:
    # Programme 150 has month 1 (120_000) and month 2 (260_000, cumulative) → keep month 2 only.
    assert _fact(_build(), 2025, "MIRES", "150").amount_cp_eur == 260_000


def test_other_groups_carry_their_latest_month() -> None:
    result = _build()
    assert _fact(result, 2025, "MIRES", "172").amount_cp_eur == 300_000
    assert _fact(result, 2024, "MIRES", "172").amount_cp_eur == 1_400_000


def test_report_accounts_for_every_row() -> None:
    report = _build().report
    assert report["source_id"] == SOURCE_ID
    assert report["rows_in"] == 4
    assert report["facts_out"] == 3
    assert report["dropped_no_exercice"] == 0
    assert report["exercices"] == [2024, 2025]
    assert report["executed"] is True


def test_registered_entry_point_matches_build() -> None:
    headers, rows = parse_csv_bytes((FIXTURES / "ods_situation_mensuelle.csv").read_bytes())
    assert get_transform(SOURCE_ID)(headers, rows).report == build(headers, rows).report


def test_rows_without_a_usable_exercice_are_dropped_and_counted() -> None:
    headers = ["Exercice", "Mois", "Code mission", "Code programme", "Dépenses nettes"]
    rows = [
        {
            "Exercice": "n/a",
            "Mois": "1",
            "Code mission": "X",
            "Code programme": "1",
            "Dépenses nettes": "5",
        }
    ]
    result = build(headers, rows)
    assert result.budget_facts == []
    assert result.report["dropped_no_exercice"] == 1
    assert result.report["facts_out"] == 0


def test_period_key_orders_numeric_then_date_like() -> None:
    # Numeric months compare by value; date-like strings sort lexically; numeric outranks date-like.
    assert _period_key("12") > _period_key("2")
    assert _period_key("2025-12") > _period_key("2025-03")
    assert _period_key("1") > _period_key("2025-03")
