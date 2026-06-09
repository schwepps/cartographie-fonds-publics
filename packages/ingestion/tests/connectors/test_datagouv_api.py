"""Offline contract test for the generic ``datagouv_api`` connector (FSC-25).

respx blocks the network, so discover/extract run against recorded fixtures; snapshot is redirected
to a tmp dir. Proves latest-millésime discovery (no frozen slug), schema-skip on a no-schema source,
provenance snapshotting, and that staging defers to FSC-35.
"""

from __future__ import annotations

from functools import partial

import httpx
import ingestion.connectors.datagouv_api as mod
import pytest
from ingestion.connectors import get_connector
from ingestion.connectors.datagouv_api import DEFAULT_API_BASE, DatagouvApiConnector
from ingestion.registry import get_source

DATASETS_URL = f"{DEFAULT_API_BASE}/datasets/"
RESOURCE_URL = "https://www.data.gouv.fr/fr/datasets/r/a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"

_SOURCE = {
    "id": "operateurs_etat",
    "discovery": {"strategy": "search_datasets(query='jaune opérateurs')"},
    "license": "Licence Ouverte 2.0",
    "schema": "none",
}


def test_discover_resolves_latest_millesime(load_fixture, respx_mock) -> None:  # type: ignore[no-untyped-def]
    respx_mock.get(DATASETS_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("datagouv_dataset_search.json"))
    )
    resolved = DatagouvApiConnector().discover(_SOURCE)
    # Picks 2025 over 2024 — by the millésime in the title, not a frozen slug.
    assert resolved["slug"] == "plf-2025-jaune-operateurs-de-letat"
    assert resolved["resource_url"] == RESOURCE_URL


def test_discover_fails_loud_on_unparseable_strategy(respx_mock) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="search query"):
        DatagouvApiConnector().discover({"id": "x", "discovery": {"strategy": "no query here"}})


def test_extract_downloads_the_resource(load_fixture, respx_mock) -> None:  # type: ignore[no-untyped-def]
    respx_mock.get(RESOURCE_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("operateurs_sample.csv"))
    )
    raw = DatagouvApiConnector().extract({"resource_url": RESOURCE_URL})
    assert raw.startswith(b"operateur")


def test_validate_skips_when_no_schema(load_fixture) -> None:  # type: ignore[no-untyped-def]
    connector = DatagouvApiConnector()
    connector.validate(load_fixture("operateurs_sample.csv"), schema_ref=None)  # no raise
    assert connector._cell_warnings == 0


def test_snapshot_writes_provenance_parquet(load_fixture, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Redirect the snapshot root (it is import-time bound) so the test never writes to data/.
    monkeypatch.setattr(mod, "write_snapshot", partial(mod.write_snapshot, root=tmp_path))
    connector = DatagouvApiConnector()
    connector._resource_url = RESOURCE_URL
    path = connector.snapshot(load_fixture("operateurs_sample.csv"), "operateurs_etat")
    assert path.endswith(".parquet")
    assert (tmp_path / "operateurs_etat" / "latest.json").is_file()


def test_stage_defers_to_fsc35() -> None:
    with pytest.raises(NotImplementedError, match="FSC-35"):
        DatagouvApiConnector().stage("snap://x", "operateurs_etat")


def test_factory_routes_the_operateurs_source() -> None:
    # The registry entry (platform: datagouv_api) resolves to this connector — no shared-file edits.
    assert isinstance(get_connector(get_source("operateurs_etat")), DatagouvApiConnector)
