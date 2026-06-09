"""Offline contract test for the generic ``ods_explore`` connector (FSC-26).

respx blocks the network, so discover/extract run against recorded fixtures; snapshot is redirected
to a tmp dir. Proves latest-exercice discovery from the registry endpoint (no frozen URL), that the
export is fetched **filtered to that exercice**, schema-skip on the ``ods_fields`` source,
provenance snapshotting, bounded/fail-loud fetching, and that staging defers to FSC-35.
"""

from __future__ import annotations

from functools import partial

import httpx
import ingestion.connectors.ods_explore as mod
import pytest
from ingestion.connectors import get_connector
from ingestion.connectors.ods_explore import OdsExploreConnector
from ingestion.registry import get_source

RECORDS_URL = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "situation-mensuelle-de-l-etat/records"
)
EXPORT_URL = RECORDS_URL.replace("/records", "/exports/csv")

_SOURCE = {
    "id": "budget_execution_mensuelle",
    "endpoint_hint": RECORDS_URL,
    "license": "Licence Ouverte 2.0",
    "schema": "ods_fields",
}


def test_discover_resolves_latest_exercice_and_filter(load_fixture, respx_mock) -> None:  # type: ignore[no-untyped-def]
    catalog = load_fixture("ods_situation_mensuelle_catalog.json")
    respx_mock.get(RECORDS_URL).mock(return_value=httpx.Response(200, content=catalog))
    resolved = OdsExploreConnector().discover(_SOURCE)
    # Picks 2025 over 2024/2023 — by the exercice read back from the data, not a frozen URL.
    assert resolved["latest_exercice"] == 2025
    assert resolved["where"] == "exercice=2025"  # discovery is consequential: it drives the filter
    assert resolved["dataset_id"] == "situation-mensuelle-de-l-etat"
    assert resolved["export_url"] == EXPORT_URL


def test_discover_fails_loud_on_missing_endpoint(respx_mock) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="endpoint_hint"):
        OdsExploreConnector().discover({"id": "x"})


def test_discover_rejects_non_http_endpoint(respx_mock) -> None:  # type: ignore[no-untyped-def]
    # A file:// or internal-host hint must fail loud, never be fetched (SSRF/scheme guard).
    bad = {"id": "x", "endpoint_hint": "file:///etc/passwd/datasets/x/records"}
    with pytest.raises(ValueError, match="endpoint_hint"):
        OdsExploreConnector().discover(bad)


def test_discover_caps_oversize_records_body(load_fixture, respx_mock, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # A misbehaving endpoint returning a huge body must fail loud, not buffer unbounded.
    monkeypatch.setattr(mod, "RECORDS_MAX_BYTES", 10)
    respx_mock.get(RECORDS_URL).mock(
        return_value=httpx.Response(
            200, content=load_fixture("ods_situation_mensuelle_catalog.json")
        )
    )
    with pytest.raises(ValueError, match="exceeded"):
        OdsExploreConnector().discover(_SOURCE)


def test_discover_fails_loud_when_no_exercice_field(respx_mock) -> None:  # type: ignore[no-untyped-def]
    # No exercice/année field in the records -> can't resolve a millésime -> fail loud, never fetch
    # an unfiltered multi-year export.
    respx_mock.get(RECORDS_URL).mock(
        return_value=httpx.Response(200, json={"results": [{"mois": 1, "code_mission": "X"}]})
    )
    with pytest.raises(ValueError, match="resolve an exercice"):
        OdsExploreConnector().discover(_SOURCE)


def test_extract_downloads_filtered_export(load_fixture, respx_mock) -> None:  # type: ignore[no-untyped-def]
    route = respx_mock.get(EXPORT_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("ods_situation_mensuelle.csv"))
    )
    raw = OdsExploreConnector().extract({"export_url": EXPORT_URL, "where": "exercice=2025"})
    assert raw.startswith(b"Exercice")
    assert route.calls.last.request.url.params.get("where") == "exercice=2025"  # filter applied


def test_extract_fails_loud_on_oversize(load_fixture, respx_mock, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Truncating an ODS export would silently drop later months and corrupt the grain — refuse it.
    monkeypatch.setattr(mod, "MAX_RESOURCE_BYTES", 10)
    respx_mock.get(EXPORT_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("ods_situation_mensuelle.csv"))
    )
    with pytest.raises(ValueError, match="exceeded"):
        OdsExploreConnector().extract({"export_url": EXPORT_URL, "where": "exercice=2025"})


def test_validate_skips_when_no_schema(load_fixture) -> None:  # type: ignore[no-untyped-def]
    connector = OdsExploreConnector()
    connector.validate(load_fixture("ods_situation_mensuelle.csv"), schema_ref=None)  # no raise
    assert connector._cell_warnings == 0


def test_snapshot_writes_provenance_parquet(load_fixture, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Redirect the snapshot root (it is import-time bound) so the test never writes to data/.
    monkeypatch.setattr(mod, "write_snapshot", partial(mod.write_snapshot, root=tmp_path))
    connector = OdsExploreConnector()
    connector._source_ref = EXPORT_URL
    raw = load_fixture("ods_situation_mensuelle.csv")
    path = connector.snapshot(raw, "budget_execution_mensuelle")
    assert path.endswith(".parquet")
    assert (tmp_path / "budget_execution_mensuelle" / "latest.json").is_file()


def test_stage_defers_to_fsc35() -> None:
    with pytest.raises(NotImplementedError, match="FSC-35"):
        OdsExploreConnector().stage("snap://x", "budget_execution_mensuelle")


def test_factory_routes_the_execution_source() -> None:
    # The registry entry (platform: ods_explore) resolves to this connector — no shared-file edits.
    assert isinstance(get_connector(get_source("budget_execution_mensuelle")), OdsExploreConnector)
