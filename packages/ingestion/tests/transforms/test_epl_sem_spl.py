"""Offline transform tests for local public companies SEM/SPL (FSC-33).

Drives ``build`` against a tiny SIRENE-derived fixture and asserts the FSC-33 contract: delegated
entities filtered to the SEM/SPL legal categories, participation edges (public shareholder →
company) emitted **only** when a shareholder is published, and the partial cases reported (golden
rule #5), never invented.
"""

from __future__ import annotations

from pathlib import Path

from core.models import EdgeType, Level
from ingestion.tabular import parse_csv_bytes
from ingestion.transforms import TransformResult, get_transform
from ingestion.transforms.epl_sem_spl import SOURCE_ID, build

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _build() -> TransformResult:
    headers, rows = parse_csv_bytes((FIXTURES / "epl_sem_spl_sample.csv").read_bytes())
    return build(headers, rows)


def test_legal_category_filter_keeps_only_sem_spl() -> None:
    result = _build()
    # The 5710 (SAS, private) row is excluded; the three 5422/5416 rows become delegated entities.
    assert {e.siren for e in result.entities} == {"552032708", "529000019", "333222115"}
    assert all(e.level is Level.delegated for e in result.entities)
    assert {e.category for e in result.entities} == {"SEM", "SPL"}


def test_participation_edges_only_when_shareholder_published() -> None:
    result = _build()
    edges = result.edges
    assert all(e.type is EdgeType.participation for e in edges)
    # Two companies carry a shareholder; the SEM with no published actionnaire yields no edge.
    assert {(e.source_siren, e.target_siren) for e in edges} == {
        ("200053781", "552032708"),  # Métropole de Lyon → SEM Lyon Confluence
        ("217500016", "529000019"),  # Ville de Paris → SPL Paris Seine Ouest
    }
    assert all(e.amount_eur is None for e in edges)  # structural link, never a fabricated amount


def test_report_accounts_for_filtered_and_partial_rows() -> None:
    report = _build().report
    assert report["source_id"] == SOURCE_ID
    assert report["entities_out"] == 3
    assert report["participation_edges"] == 2
    assert report["filtered_out_category"] == 1  # the SAS row
    assert report["without_shareholder"] == 1  # the SEM with no published actionnaire
    assert report["unresolved_company_siren"] == 0


def test_registered_entry_point_matches_build() -> None:
    headers, rows = parse_csv_bytes((FIXTURES / "epl_sem_spl_sample.csv").read_bytes())
    assert get_transform(SOURCE_ID)(headers, rows).report == build(headers, rows).report
