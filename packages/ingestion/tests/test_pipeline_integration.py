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
from ingestion.load import ALL_SOURCE_IDS, LoadBundle, emit_load_sql
from ingestion.snapshot import write_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_MIGRATIONS = _REPO_ROOT / "supabase" / "migrations"
_ROLES_SHIM = _REPO_ROOT / "supabase" / "tests" / "supabase_roles.sql"
_RLS_CHECKS = _REPO_ROOT / "supabase" / "tests" / "rls_checks.sql"
_EXTRACTED_AT = "2026-06-09T00:00:00+00:00"

# The operators sample resolves 3 of 5 rows against the committed crosswalk (2 are deliberately
# unresolvable); the full population's target is FSC-56's ≥90%. Here we only guard against a
# regression of the load path itself, so a conservative floor is right.
_MATCH_RATE_MIN = 0.5

# A throwaway database in the same cluster as DATABASE_URL — created and dropped by this module so
# the run is disposable and never mutates the caller's graph.
_IT_DBNAME = "cfp_pipeline_it"

# source_id -> committed fixture. État-central + social reuse the per-connector samples (already a
# coherent slice). OFGL uses the dedicated integration fixture (see module docstring).
_FIXTURE_BY_SOURCE: dict[str, Path] = {
    "operateurs_etat": _REPO_ROOT
    / "spikes/phase0_siren_match/fixtures/operateurs_resolve_sample.csv",
    "finances_locales_ofgl": _FIXTURES / "integration" / "ofgl.csv",
    "comptes_sociaux": _FIXTURES / "comptes_sociaux_sample.csv",
    "budget_plf_lfi": _FIXTURES / "plf_depenses_sample.csv",
    "budget_execution_mensuelle": _FIXTURES / "ods_situation_mensuelle.csv",
    "decp_commande_publique": _FIXTURES / "decp_consolidated_sample.csv",
    "epl_sem_spl": _FIXTURES / "epl_sem_spl_sample.csv",
}

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
def loaded(pipeline_db: str, tmp_path_factory: pytest.TempPathFactory) -> tuple[str, LoadBundle]:
    """Snapshot every source from its fixture, render the whole-perimeter load, and apply it."""
    url = pipeline_db
    snapshot_root = tmp_path_factory.mktemp("snapshots")
    for source_id, fixture in _FIXTURE_BY_SOURCE.items():
        write_snapshot(
            fixture.read_bytes(),
            source_id=source_id,
            extracted_at=_EXTRACTED_AT,
            root=snapshot_root,
        )
    load_sql, bundle = emit_load_sql(
        snapshot_root / "load.sql", source_ids=ALL_SOURCE_IDS, snapshot_root=snapshot_root
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
    # `set role` precedes the SELECT in one session; psql prints its `SET` tag first, so read the
    # final line (the count) walked as the anon role through the public RPC the UI calls.
    out = _psql(
        url,
        sql="set role anon; "
        "select count(*) from graph_neighbors("
        "(select source_siren from edges where provenance = 'operateurs_etat' limit 1), 1)",
    )
    assert int(out.splitlines()[-1]) >= 1
