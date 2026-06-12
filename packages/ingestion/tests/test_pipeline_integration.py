"""End-to-end pipeline integration test (FSC-57): ingest → resolve → load → read.

Loads **all** curated sources — state operators, local OFGL collectivités, social accounts, PLF +
execution budget, DECP contracts, and SEM/SPL participations — from committed fixtures through the
real loader into a **disposable** Postgres, then asserts the *combined* graph is coherent. This is
the cross-connector regression net the per-transform unit tests can't be: it catches a slice that is
fine in isolation but produces an orphan edge, a match-rate regression, or a broken read path once
merged with the others.

Asserts:
  * every curated table populates (entities / edges / budget_facts / contracts);
  * **no orphan edges** — every edge endpoint resolves to a loaded entity;
  * the operator SIREN match-rate clears the threshold;
  * the RLS public-read path works (anon SELECT + ``graph_neighbors``) and writes are blocked.

Skipped unless ``DATABASE_URL`` + ``psql`` are present, so offline ``pytest`` and the ``python`` CI
job stay green; it runs in the CI ``database`` job, which provides Postgres. The test creates and
drops its **own** database, so it never touches the caller's data (disposable, per the AC).

The slice reuses the per-connector sample fixtures where they are already a coherent cross-source
slice (DECP's acheteurs are the seeded operators, etc.). OFGL uses a dedicated
``fixtures/integration/ofgl.csv`` whose collectivités include the SEM/SPL shareholders — the shared
``ofgl_sample.csv`` omits *Métropole de Lyon* (a participation-edge source), which would orphan that
edge here even though production OFGL carries every collectivité. The orphan assertion is kept
strict; the fixture is made coherent (mirroring production), never the assertion weakened.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
from core.methodology import universe_for_nomenclature
from core.models import Nomenclature
from ingestion.load import ALL_SOURCE_IDS, LoadBundle, emit_load_sql

# The whole-perimeter fixture slice + drift guard live in conftest (whole_perimeter_snapshot_root),
# so this DB test and the offline `test_reconciliation` reconcile the *same* cross-source data.

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MIGRATIONS = _REPO_ROOT / "supabase" / "migrations"
_ROLES_SHIM = _REPO_ROOT / "supabase" / "tests" / "supabase_roles.sql"
_RLS_CHECKS = _REPO_ROOT / "supabase" / "tests" / "rls_checks.sql"

# The operators sample resolves 3 of 5 rows against the committed crosswalk (2 are deliberately
# unresolvable); the full population's target is FSC-56's ≥90%. Here we only guard against a
# regression of the load path itself, so a conservative floor is right.
_MATCH_RATE_MIN = 0.5

# A throwaway database in the same cluster as DATABASE_URL — created and dropped by this module so
# the run is disposable and never mutates the caller's graph.
_IT_DBNAME = "cfp_pipeline_it"

_DATABASE_URL = os.environ.get("DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not _DATABASE_URL or shutil.which("psql") is None,
    reason="needs DATABASE_URL + psql (runs in the CI `database` job)",
)


def _psql(url: str, *, sql: str | None = None, file: Path | None = None) -> str:
    """Run one psql command (``-c`` SQL or ``-f`` file); fail loud with stderr on a nonzero exit."""
    cmd = ["psql", url, "-v", "ON_ERROR_STOP=1", "-tA"]
    if sql is not None:
        cmd += ["-c", sql]
    if file is not None:
        cmd += ["-f", str(file)]
    proc = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603 (trusted args)
    if proc.returncode != 0:
        raise AssertionError(f"psql failed ({proc.returncode}):\n{proc.stderr}\n{proc.stdout}")
    return proc.stdout.strip()


def _count(url: str, sql: str) -> int:
    return int(_psql(url, sql=sql))


def _with_dbname(url: str, dbname: str) -> str:
    return urlunparse(urlparse(url)._replace(path=f"/{dbname}"))


@pytest.fixture(scope="module")
def pipeline_db() -> Iterator[str]:
    """A fresh, migrated, Supabase-shimmed database — created and dropped per module run."""
    assert _DATABASE_URL  # narrowed by pytestmark
    admin = _DATABASE_URL
    _psql(admin, sql=f"drop database if exists {_IT_DBNAME} with (force)")
    _psql(admin, sql=f"create database {_IT_DBNAME}")
    url = _with_dbname(admin, _IT_DBNAME)
    try:
        # Roles + grants BEFORE the migrations, so the tables they create inherit the grants and RLS
        # (not a missing GRANT) is what the read-path assertions actually test — same order as CI.
        _psql(url, file=_ROLES_SHIM)
        for migration in sorted(_MIGRATIONS.glob("*.sql")):
            _psql(url, file=migration)
        yield url
    finally:
        _psql(admin, sql=f"drop database if exists {_IT_DBNAME} with (force)")


@pytest.fixture(scope="module")
def loaded(pipeline_db: str, whole_perimeter_snapshot_root: Path) -> tuple[str, LoadBundle]:
    """Render the whole-perimeter load from the shared fixture slice and apply it to the DB."""
    url = pipeline_db
    load_sql, bundle = emit_load_sql(
        whole_perimeter_snapshot_root / "load.sql",
        source_ids=ALL_SOURCE_IDS,
        snapshot_root=whole_perimeter_snapshot_root,
    )
    _psql(url, file=load_sql)
    return url, bundle


def test_all_curated_tables_populate(loaded: tuple[str, LoadBundle]) -> None:
    url, _ = loaded
    for table in ("entities", "edges", "budget_facts", "contracts"):
        assert _count(url, f"select count(*) from {table}") > 0, f"{table} empty after full load"


def test_no_orphan_edges(loaded: tuple[str, LoadBundle]) -> None:
    """Every edge endpoint must resolve to a loaded entity — the core cross-connector invariant."""
    url, _ = loaded
    orphans = _count(
        url,
        "select count(*) from edges e "
        "where not exists (select 1 from entities en where en.siren = e.source_siren) "
        "or not exists (select 1 from entities en where en.siren = e.target_siren)",
    )
    assert orphans == 0, f"{orphans} orphan edge endpoint(s) — an edge points at no loaded entity"


def test_all_edge_types_present(loaded: tuple[str, LoadBundle]) -> None:
    """The merged graph carries every cross-source edge kind (tutelle/delegates/participation)."""
    url, _ = loaded
    types = set(_psql(url, sql="select distinct type from edges").splitlines())
    assert {"tutelle", "delegates", "participation"} <= types


def test_operator_siren_match_rate(loaded: tuple[str, LoadBundle]) -> None:
    _, bundle = loaded
    rate = float(bundle.reports["operateurs_etat"]["resolution_rate"])
    assert rate >= _MATCH_RATE_MIN, f"operator SIREN match-rate {rate:.0%} < {_MATCH_RATE_MIN:.0%}"


def test_rls_public_read_and_writes_blocked(loaded: tuple[str, LoadBundle]) -> None:
    """anon can SELECT every table + call the RPC, but INSERT/UPDATE/DELETE are blocked."""
    url, _ = loaded
    _psql(url, file=_RLS_CHECKS)  # self-contained, rolled back; raises on any RLS breach


def test_graph_neighbors_reachable_as_anon(loaded: tuple[str, LoadBundle]) -> None:
    """A loaded tutelle edge is walkable through the public RPC the UI calls, as the anon role."""
    url, _ = loaded
    # `set role` precedes the SELECT in one session; psql also prints its `SET` tag, so pick the
    # numeric line — the neighbour count walked as anon through the public RPC the UI calls.
    out = _psql(
        url,
        sql="set role anon; "
        "select count(*) from graph_neighbors("
        "(select source_siren from edges where provenance = 'operateurs_etat' limit 1), 1)",
    )
    counts = [int(line) for line in out.splitlines() if line.strip().isdigit()]
    assert counts and counts[-1] >= 1


# --- Anti-double-counting reconciliation on the actually-loaded data (FSC-58) ----------------


def _universe_sums(url: str) -> dict[str, float]:
    """Per-universe CP totals of the loaded ``budget_facts`` (m14 folds into M57), mapped through
    the authoritative ``core.methodology`` nomenclature→universe convention."""
    out = _psql(
        url,
        sql="select nomenclature, coalesce(sum(amount_cp_eur), 0) from budget_facts "
        "group by nomenclature",
    )
    totals: dict[str, float] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        nomenclature, total = line.split("|")
        universe = universe_for_nomenclature(Nomenclature(nomenclature))
        totals[universe] = totals.get(universe, 0.0) + float(total)
    return totals


def test_every_budget_fact_carries_a_universe(loaded: tuple[str, LoadBundle]) -> None:
    """The partition key is always present on loaded rows — no fact can escape the reconciliation by
    landing in a NULL/unknown universe (the 0006 CHECK constraint backstops the allowed values)."""
    url, _ = loaded
    missing = _count(url, "select count(*) from budget_facts where nomenclature is null")
    assert missing == 0, f"{missing} loaded budget_facts row(s) carry no nomenclature"


def test_per_universe_sums_partition_the_loaded_total(loaded: tuple[str, LoadBundle]) -> None:
    """AC2 on actually-loaded data: grouping ``budget_facts`` by accounting universe reconciles to
    the grand CP total exactly (no row dropped), and the combined load spans >1 universe. The
    breakdown is printed so any residual is visible in CI logs, never hidden (golden rule #8)."""
    url, _ = loaded
    totals = _universe_sums(url)
    grand = float(_psql(url, sql="select coalesce(sum(amount_cp_eur), 0) from budget_facts"))
    print("\nPer-universe CP reconciliation (loaded budget_facts):")
    for universe, total in sorted(totals.items()):
        print(f"  {universe}: {total:,.0f} €")
    print(f"  Σ universes = {sum(totals.values()):,.0f} €   (grand total = {grand:,.0f} €)")
    assert sum(totals.values()) == pytest.approx(grand)
    assert len(totals) > 1, "combined load should span more than one accounting universe"


def test_transfers_live_in_edges_not_in_budget_facts(loaded: tuple[str, LoadBundle]) -> None:
    """AC1 structural on loaded data: the funding/delegation hops are ``edges`` (and ``contracts``),
    disjoint from the entity-keyed ``budget_facts``. A transfer amount has no column to land in on
    ``budget_facts`` (no source→target pair), so it can never be summed into a universe total — the
    per-universe sums come solely from ``budget_facts``."""
    url, _ = loaded
    hop_edges = _count(url, "select count(*) from edges where type in ('funds', 'delegates')")
    assert hop_edges >= 1, "no funding/delegation edges loaded — the hop layer is missing"
    cols = set(
        _psql(
            url,
            sql="select column_name from information_schema.columns "
            "where table_name = 'budget_facts'",
        ).splitlines()
    )
    assert "source_siren" not in cols and "target_siren" not in cols
    assert "amount_cp_eur" in cols
