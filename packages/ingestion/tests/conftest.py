"""Shared pytest fixtures for the ingestion test suite.

These power the offline connector contract-test harness: a fixtures loader plus
respx's own ``respx_mock`` fixture (registered automatically by the respx pytest
plugin) give every connector test recorded HTTP with no network. See
``connectors/README.md`` for the full template.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from ingestion.load import ALL_SOURCE_IDS
from ingestion.snapshot import write_snapshot

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# --- Whole-perimeter (all 4 layers) slice, shared by the offline reconciliation test and the DB
# pipeline test (FSC-57/FSC-58) so both reconcile the SAME coherent cross-source data. ---

_REPO_ROOT = Path(__file__).resolve().parents[3]
WHOLE_PERIMETER_EXTRACTED_AT = "2026-06-09T00:00:00+00:00"

# source_id -> committed fixture. État-central + social reuse the per-connector samples (already a
# coherent slice). OFGL uses the dedicated integration fixture whose collectivités include the
# SEM/SPL shareholders (the shared sample omits Métropole de Lyon, which would orphan that edge).
_FIXTURE_BY_SOURCE: dict[str, Path] = {
    "operateurs_etat": _REPO_ROOT
    / "spikes/phase0_siren_match/fixtures/operateurs_resolve_sample.csv",
    "finances_locales_ofgl": FIXTURES_DIR / "integration" / "ofgl.csv",
    "comptes_sociaux": FIXTURES_DIR / "comptes_sociaux_sample.csv",
    "budget_plf_lfi": FIXTURES_DIR / "plf_depenses_sample.csv",
    "budget_execution_mensuelle": FIXTURES_DIR / "ods_situation_mensuelle.csv",
    "decp_commande_publique": FIXTURES_DIR / "decp_consolidated_sample.csv",
    "epl_sem_spl": FIXTURES_DIR / "epl_sem_spl_sample.csv",
}

# Collection-time guard: the fixtures must cover exactly the sources the whole-perimeter load spans,
# so a source added to ALL_SOURCE_IDS without a fixture (or vice-versa) can't silently under-test.
# Centralised here so the two whole-perimeter tests provably load the *same* slice (not two copies
# that could drift to different fixtures for the same source).
assert set(_FIXTURE_BY_SOURCE) == set(ALL_SOURCE_IDS), (
    "whole-perimeter fixtures must cover every source in ALL_SOURCE_IDS: "
    f"{set(ALL_SOURCE_IDS) ^ set(_FIXTURE_BY_SOURCE)} mismatched"
)


@pytest.fixture(scope="module")
def whole_perimeter_snapshot_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A snapshot tree with every whole-perimeter source written from its committed fixture — the
    one slice the offline reconciliation and the DB pipeline test both load."""
    root = tmp_path_factory.mktemp("snapshots")
    for source_id, fixture in _FIXTURE_BY_SOURCE.items():
        write_snapshot(
            fixture.read_bytes(),
            source_id=source_id,
            extracted_at=WHOLE_PERIMETER_EXTRACTED_AT,
            root=root,
        )
    return root


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to the shared connector-test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def load_fixture() -> Callable[[str], bytes]:
    """Return a loader that reads a fixture file's raw bytes by name.

    Usage::

        def test_discovery(load_fixture, respx_mock):
            payload = load_fixture("datagouv_dataset_search.json")
    """

    def _load(name: str) -> bytes:
        path = FIXTURES_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f"Fixture not found: {path}")
        return path.read_bytes()

    return _load
