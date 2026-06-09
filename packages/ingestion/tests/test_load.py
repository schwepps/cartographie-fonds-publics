"""Tests for the curated État-central loader (FSC-35).

Offline, no DB: the loader's core (snapshot read -> transform -> merge -> SQL render) is pure, so
these pin the contract without touching Postgres. The end-to-end DB apply (idempotent counts +
``graph_neighbors`` visibility) is exercised by the CI ``database`` job against a real Postgres.

Coverage:
* ``read_snapshot_rows`` round-trips a ``write_snapshot`` Parquet faithfully (all-varchar, so SIREN
  leading zeros survive — the same contract a live CSV would honour);
* ``build_bundle`` merges the three sources, drops + counts unresolved entities, stamps provenance,
  keeps voted/executed budget facts distinct, and dedups entities by SIREN;
* the empty/destructive guard fails loud (a 0-row source would wipe its rows on reload);
* ``render_load_sql`` is deterministic + idempotent and emits the provenance-scoped contract
  (entity upsert on SIREN, delete-by-provenance for edges/budget_facts).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core.models import Edge, EdgeType, Entity, Level
from ingestion.errors import LoadError
from ingestion.load import (
    ETAT_CENTRAL_SOURCE_IDS,
    LoadBundle,
    build_bundle,
    load_summary,
    render_load_sql,
)
from ingestion.snapshot import read_snapshot_rows, write_snapshot
from ingestion.transforms.operateurs_etat import MINISTRY_CATEGORY

# The operators sample `make operators` uses (resolves against the committed crosswalk). Budget
# samples live in the shared connector-test fixtures dir (see conftest `fixtures_dir`).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPERATORS_FIXTURE = _REPO_ROOT / "spikes/phase0_siren_match/fixtures/operateurs_resolve_sample.csv"
_EXTRACTED_AT = "2026-06-09T00:00:00+00:00"


def _seed_snapshots(root: Path, fixtures_dir: Path) -> Path:
    """Write a snapshot per État-central source from the committed fixtures into ``root``."""
    sources = {
        "operateurs_etat": _OPERATORS_FIXTURE,
        "budget_plf_lfi": fixtures_dir / "plf_depenses_sample.csv",
        "budget_execution_mensuelle": fixtures_dir / "ods_situation_mensuelle.csv",
    }
    for source_id, path in sources.items():
        write_snapshot(
            path.read_bytes(), source_id=source_id, extracted_at=_EXTRACTED_AT, root=root
        )
    return root


# --------------------------------------------------------------------------- #
# read_snapshot_rows
# --------------------------------------------------------------------------- #
def test_read_snapshot_rows_round_trips_all_varchar(tmp_path: Path) -> None:
    raw = b"siren;name\n0123;Alpha\n;Beta\n"  # leading zero + an empty cell
    write_snapshot(raw, source_id="demo", extracted_at=_EXTRACTED_AT, root=tmp_path)
    headers, rows = read_snapshot_rows("demo", root=tmp_path)
    assert headers == ["siren", "name"]
    # Leading-zero SIREN preserved (all-varchar); empty cell becomes "" (parse_csv_bytes parity).
    assert rows == [{"siren": "0123", "name": "Alpha"}, {"siren": "", "name": "Beta"}]


def test_read_snapshot_rows_fails_loud_when_missing(tmp_path: Path) -> None:
    from ingestion.errors import SnapshotError

    with pytest.raises(SnapshotError, match="No snapshot pointer"):
        read_snapshot_rows("never_snapshotted", root=tmp_path)


# --------------------------------------------------------------------------- #
# build_bundle — merge, dedup, provenance, unresolved accounting
# --------------------------------------------------------------------------- #
def test_build_bundle_merges_three_sources(tmp_path: Path, fixtures_dir: Path) -> None:
    root = _seed_snapshots(tmp_path, fixtures_dir)
    bundle = build_bundle(snapshot_root=root)

    # Entities: all loaded rows carry a SIREN (unresolved are dropped), unique by SIREN, État level.
    assert bundle.entities
    assert all(e.siren is not None for e in bundle.entities)
    sirens = [e.siren for e in bundle.entities]
    assert len(sirens) == len(set(sirens))  # deduped by SIREN
    assert all(e.level is Level.state for e in bundle.entities)
    ministries = [e for e in bundle.entities if e.category == MINISTRY_CATEGORY]
    assert ministries and all(m.parent_siren is None for m in ministries)

    # Unresolved operators are dropped from the load but accounted for (golden rule #5): the count
    # equals the operators transform's reported unresolved tally — never silently lost.
    assert bundle.skipped_unresolved == bundle.reports["operateurs_etat"]["unresolved"]

    # Edges: tutelle only here, all stamped with the operators source as provenance.
    assert bundle.edges
    assert all(e.type.value == "tutelle" for e in bundle.edges)
    assert all(e.provenance == "operateurs_etat" for e in bundle.edges)

    # Budget facts: voted from PLF, executed from the monthly situation — kept distinct, each
    # stamped with its own source provenance.
    voted = [f for f in bundle.budget_facts if not f.executed]
    executed = [f for f in bundle.budget_facts if f.executed]
    assert voted and executed
    assert all(f.provenance == "budget_plf_lfi" for f in voted)
    assert all(f.provenance == "budget_execution_mensuelle" for f in executed)

    assert bundle.provenances == ETAT_CENTRAL_SOURCE_IDS


def test_load_summary_reports_counts(tmp_path: Path, fixtures_dir: Path) -> None:
    bundle = build_bundle(snapshot_root=_seed_snapshots(tmp_path, fixtures_dir))
    summary = load_summary(bundle)
    assert "entities:" in summary and "edges:" in summary and "budget_facts:" in summary
    assert "resolution rate" in summary  # surfaced from the operators report


# --------------------------------------------------------------------------- #
# Empty / destructive guard
# --------------------------------------------------------------------------- #
def test_empty_source_is_refused(tmp_path: Path) -> None:
    # A header-only PLF snapshot the transform accepts but that yields 0 facts. Reloading it would
    # delete the source's existing rows with nothing to re-insert — must fail loud.
    headers = ["exercice", "mission", "programme", "AE", "CP"]

    def read_rows(_source_id: str) -> tuple[list[str], list[dict[str, str]]]:
        return headers, []

    with pytest.raises(LoadError, match="0 curated rows"):
        build_bundle(("budget_plf_lfi",), read_rows=read_rows)

    # allow_empty overrides for the (rare) legitimate empty case.
    bundle = build_bundle(("budget_plf_lfi",), read_rows=read_rows, allow_empty=True)
    assert bundle.budget_facts == []


# --------------------------------------------------------------------------- #
# render_load_sql — determinism, idempotency, the provenance-scoped contract
# --------------------------------------------------------------------------- #
def test_render_is_deterministic_and_idempotent(tmp_path: Path, fixtures_dir: Path) -> None:
    root = _seed_snapshots(tmp_path, fixtures_dir)
    first = render_load_sql(build_bundle(snapshot_root=root))
    second = render_load_sql(build_bundle(snapshot_root=root))
    assert first == second  # byte-identical re-render => re-applying is a no-op on row counts


def test_render_emits_provenance_scoped_contract(tmp_path: Path, fixtures_dir: Path) -> None:
    sql = render_load_sql(build_bundle(snapshot_root=_seed_snapshots(tmp_path, fixtures_dir)))
    assert sql.startswith("-- out/load.sql")
    assert "begin;" in sql and sql.rstrip().endswith("commit;")
    # Entities upsert on the canonical SIREN (accretive), never deleted.
    assert "on conflict (siren) do update set" in sql
    assert "delete from entities" not in sql
    # Each table's DELETE is scoped to ONLY the provenances that produced rows of that table —
    # the edge DELETE never names a budget source, and vice versa (the contract the docstring
    # promises: another source's rows are never touched).
    assert "delete from edges where provenance in ('operateurs_etat');" in sql
    assert (
        "delete from budget_facts where provenance in "
        "('budget_execution_mensuelle', 'budget_plf_lfi');" in sql
    )
    # Only the three owned tables are touched — no whole-table truncate, no other tables.
    assert "truncate" not in sql
    assert "contracts" not in sql and "attributions" not in sql


def test_render_skips_delete_for_a_table_with_no_rows() -> None:
    # A degraded operators load: entities resolved but ZERO edges (e.g. the tutelle column drifted
    # so no ministry resolves). The rebuild must NOT delete edges — wiping the live tutelle layer
    # with no replacement is exactly the destructive failure per-table scoping guards against.
    bundle = LoadBundle(
        entities=[
            Entity(
                siren="110000072",
                name="Ministère X",
                level=Level.state,
                category=MINISTRY_CATEGORY,
                provenance="operateurs_etat",
            )
        ],
        edges=[],
        budget_facts=[],
        provenances=("operateurs_etat",),
        skipped_unresolved=0,
        reports={},
    )
    sql = render_load_sql(bundle)
    assert "on conflict (siren) do update set" in sql  # entities still upserted
    assert "delete from edges" not in sql  # nothing produced this run -> nothing deleted
    assert "delete from budget_facts" not in sql


def test_render_fails_loud_on_row_missing_provenance() -> None:
    # A row without provenance would be inserted yet fall in no delete scope, silently breaking
    # idempotency on the next reload — the loader must refuse it rather than load it.
    bundle = LoadBundle(
        entities=[],
        edges=[
            Edge(
                source_siren="110000072",
                target_siren="130005481",
                type=EdgeType.tutelle,
                provenance=None,
            )
        ],
        budget_facts=[],
        provenances=("operateurs_etat",),
        skipped_unresolved=0,
        reports={},
    )
    with pytest.raises(LoadError, match="missing provenance"):
        render_load_sql(bundle)
