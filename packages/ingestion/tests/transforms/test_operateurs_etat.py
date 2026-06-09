"""Offline transform tests for the Jaune operators (FSC-25).

Drives ``build`` against tiny fixtures: an operators CSV, a sample crosswalk, and a sample ministry
reference. Asserts the golden-rule-#5 contract — operators become entities, tutelle edges link
ministry->operator only when both ends carry a SIREN, the resolution rate is reported, and no input
is ever dropped (resolved + unresolved == total).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core.crosswalk import CrosswalkEntry, CrosswalkStatus
from core.models import Edge, EdgeType, Entity, Level
from ingestion.crosswalk_io import load_crosswalk, load_ministries
from ingestion.tabular import parse_csv_bytes
from ingestion.transforms import TransformResult, get_transform
from ingestion.transforms.operateurs_etat import MinistryIndex, build

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _build() -> TransformResult:
    headers, rows = parse_csv_bytes((FIXTURES / "operateurs_transform_sample.csv").read_bytes())
    crosswalk = load_crosswalk(FIXTURES / "crosswalk_sample.yaml")
    ministries = MinistryIndex.load(FIXTURES / "ministeres_sample.yaml")
    return build(headers, rows, crosswalk=crosswalk, ministries=ministries)


def _build_jaune() -> TransformResult:
    """Build against the realistic dual-name-column Jaune shape (leaf + grouping + category)."""
    headers, rows = parse_csv_bytes((FIXTURES / "operateurs_jaune_sample.csv").read_bytes())
    crosswalk = load_crosswalk(FIXTURES / "crosswalk_sample.yaml")
    ministries = MinistryIndex.load(FIXTURES / "ministeres_sample.yaml")
    return build(headers, rows, crosswalk=crosswalk, ministries=ministries)


def _operator_names(result: TransformResult) -> set[str]:
    return {e.name for e in result.entities if e.category != "ministère"}


def test_operators_become_state_entities_with_category() -> None:
    result = _build()
    operators = [e for e in result.entities if e.category != "ministère"]
    assert {e.name for e in operators} == {
        "Agence Alpha",
        "Agence Beta",
        "Agence Pending",
        "Agence Inconnue",
    }
    assert all(e.level is Level.state for e in result.entities)
    alpha = next(e for e in operators if e.name == "Agence Alpha")
    assert alpha.siren == "111111118"  # resolved via crosswalk
    assert alpha.parent_siren == "900000017"  # tutelle ministry AA
    assert alpha.category == "EPA"


def test_ministries_emitted_and_deduplicated() -> None:
    result = _build()
    ministries = [e for e in result.entities if e.category == "ministère"]
    # AA (referenced by Alpha + Pending) and GG (referenced by Inconnue) resolve; ZZ does not.
    assert {e.siren for e in ministries} == {"900000017", "900000025"}
    assert all(e.level is Level.state for e in ministries)


def test_tutelle_edge_only_when_both_ends_have_a_siren() -> None:
    result = _build()
    # Only Agence Alpha is both SIREN-resolved AND has a resolvable ministry (AA).
    assert len(result.edges) == 1
    edge = result.edges[0]
    assert isinstance(edge, Edge)
    assert edge.source_siren == "900000017"  # ministry
    assert edge.target_siren == "111111118"  # operator
    assert edge.type is EdgeType.tutelle
    assert edge.provenance == "operateurs_etat"


def test_resolved_operator_with_missing_ministry_has_no_edge_and_no_parent() -> None:
    result = _build()
    beta = next(e for e in result.entities if e.name == "Agence Beta")
    assert beta.siren == "222222226"  # resolved
    assert beta.parent_siren is None  # tutelle ZZ not in the ministry reference
    assert all(e.target_siren != "222222226" for e in result.edges)  # no tutelle edge


def test_no_silent_drops() -> None:
    result = _build()
    report = result.report
    assert report["total"] == 4
    assert report["resolved"] + report["unresolved"] == report["total"]
    assert report["resolution_rate"] == pytest.approx(0.5)
    # Every operator row is present as an entity — unresolved ones kept with siren=None.
    operators = [e for e in result.entities if e.category != "ministère"]
    assert len(operators) == 4
    assert {e.name for e in operators if e.siren is None} == {
        "Agence Pending",
        "Agence Inconnue",
    }


def test_unresolved_surface_in_report_with_reasons() -> None:
    result = _build()
    links = {link["denomination"]: link["reason"] for link in result.report["unresolved_links"]}
    assert links == {
        "Agence Pending": "multiple_candidates",  # pending row carrying >1 candidate SIREN
        "Agence Inconnue": "no_siren_no_crosswalk",  # no crosswalk row at all
    }


def test_emitted_entities_validate_against_frozen_model() -> None:
    result = _build()
    # build() constructs Entity/Edge instances, so re-validation must round-trip without error.
    for entity in result.entities:
        Entity.model_validate(entity.model_dump())
    for edge in result.edges:
        Edge.model_validate(edge.model_dump())


def test_registered_transform_resolves_against_committed_data() -> None:
    # The registry entry point loads the committed crosswalk + ministeres.yaml (CNRS/BnF/France
    # Travail resolve; their tutelle ministries exist) — proves real data wires end to end.
    headers, rows = parse_csv_bytes(
        (
            Path(__file__).resolve().parents[4]
            / "spikes"
            / "phase0_siren_match"
            / "fixtures"
            / "operateurs_resolve_sample.csv"
        ).read_bytes()
    )
    result = get_transform("operateurs_etat")(headers, rows)
    assert result.report["resolved"] == 3
    assert result.report["tutelle_edges"] == 3


def test_ministry_index_resolves_by_code_then_name() -> None:
    index = MinistryIndex.load(FIXTURES / "ministeres_sample.yaml")

    def _siren(value: str | None) -> str | None:
        entry = index.resolve(value)
        return entry.siren if entry else None

    assert _siren("AA") == "900000017"  # by code
    assert _siren("aa") == "900000017"  # code is case-insensitive
    assert _siren("Ministère Alpha") == "900000017"  # by normalized name
    assert index.resolve("ZZ") is None
    assert index.resolve("") is None
    assert index.resolve(None) is None


def test_load_ministries_fails_loud_on_missing_code(tmp_path: Path) -> None:
    bad = tmp_path / "m.yaml"
    bad.write_text(
        "schema_version: 1\nentries:\n"
        "- denomination: X\n  status: reviewed\n  siren: '900000017'\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="tutelle code"):
        load_ministries(bad)


def test_load_ministries_fails_loud_on_duplicate_code(tmp_path: Path) -> None:
    bad = tmp_path / "m.yaml"
    bad.write_text(
        "schema_version: 1\nentries:\n"
        "- denomination: X\n  status: reviewed\n  siren: '900000017'\n  tutelle: AA\n"
        "- denomination: Y\n  status: reviewed\n  siren: '900000025'\n  tutelle: AA\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate ministry tutelle code"):
        load_ministries(bad)


def test_load_ministries_rejects_non_reviewed_status(tmp_path: Path) -> None:
    # The ministry reference is hand-curated, never generated — an `auto` row must fail loud.
    bad = tmp_path / "m.yaml"
    bad.write_text(
        "schema_version: 1\nentries:\n"
        "- denomination: X\n  status: auto\n  siren: '900000017'\n  tutelle: AA\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be 'reviewed'"):
        load_ministries(bad)


def test_ministry_index_rejects_name_collision() -> None:
    # Two ministries normalizing to the same name must not silently resolve to one SIREN.
    entries = [
        CrosswalkEntry(
            denomination="Ministère X",
            status=CrosswalkStatus.reviewed,
            siren="900000017",
            tutelle="A",
        ),
        CrosswalkEntry(
            denomination="Ministère X",
            status=CrosswalkStatus.reviewed,
            siren="900000025",
            tutelle="B",
        ),
    ]
    with pytest.raises(ValueError, match="name collision"):
        MinistryIndex(entries)


# --------------------------------------------------------------------------- #
# Realistic Jaune shape: dual name columns (leaf + grouping), category column, edge dedup
# --------------------------------------------------------------------------- #
def test_dual_name_columns_coalesce_leaf_over_grouping() -> None:
    names = _operator_names(_build_jaune())
    # Leaf wins when present (row carries grouping "Universités…" AND leaf "Agence Alpha").
    assert "Agence Alpha" in names
    # Grouping is used when the leaf is blank (Beta has only a leaf; Pending only a grouping).
    assert "Agence Beta" in names  # grouping blank, leaf present
    assert "Agence Pending" in names  # leaf blank, grouping fills
    # The standalone grouping with no leaf is a category label, kept by its own name.
    assert "Universités et assimilés" in names


def test_category_column_detected_not_mistaken_for_a_name_column() -> None:
    result = _build_jaune()
    alpha = next(e for e in result.entities if e.name == "Agence Alpha")
    # Category comes from "Catégorie juridique", not the grouping label that also says "catégorie".
    assert alpha.category == "EPA"


def test_category_label_tier_kept_as_entity_and_reported() -> None:
    result = _build_jaune()
    label = next(e for e in result.entities if e.name == "Universités et assimilés")
    assert label.siren is None  # a category label has no own SIREN, by design — kept, not dropped
    reasons = {link["denomination"]: link["reason"] for link in result.report["unresolved_links"]}
    assert reasons["Universités et assimilés"] == "category_label"


def test_blank_row_is_skipped_not_dropped() -> None:
    result = _build_jaune()
    # 4 distinct operators (the all-blank row adds nothing; the duplicate Alpha collapses to one).
    assert result.report["total"] == 4
    assert result.report["operators"] == 4


def test_duplicate_operator_rows_yield_one_entity_and_one_edge() -> None:
    result = _build_jaune()
    alphas = [e for e in result.entities if e.name == "Agence Alpha"]
    assert len(alphas) == 1  # the two identical Jaune rows collapse to a single entity
    assert alphas[0].siren == "111111118"
    alpha_edges = [e for e in result.edges if e.target_siren == "111111118"]
    assert len(alpha_edges) == 1  # and a single tutelle edge
