"""Offline tests for the Phase-0 live spike.

The data.gouv.fr catalog, the resource downloads, and the (misconfigured) DECP schema ref are
all replayed from recorded fixtures via respx — the run is fully deterministic and offline.
"""

from __future__ import annotations

import httpx
import pytest
import spike
from ingestion.registry import Source, get_source

API_BASE = "https://www.data.gouv.fr/api/1"
DATASETS_URL = f"{API_BASE}/datasets/"


# --------------------------------------------------------------------------- #
# Unit-level helpers
# --------------------------------------------------------------------------- #
def test_to_siren_accepts_siren_and_reduces_siret() -> None:
    assert spike.to_siren("180089013") == "180089013"  # plain SIREN
    assert spike.to_siren("180 089 013") == "180089013"  # spaced SIREN
    assert spike.to_siren("18008901300010") == "180089013"  # SIRET -> first 9 = SIREN
    assert spike.to_siren("12345") is None  # too short
    assert spike.to_siren("SIRET") is None  # non-numeric
    assert spike.to_siren(None) is None


def test_query_from_strategy_handles_inner_apostrophe() -> None:
    source = Source(
        id="operateurs_etat",
        raw={"discovery": {"strategy": "search_datasets(query='jaune opérateurs de l'État'); x"}},
    )
    assert spike.query_from_strategy(source) == "jaune opérateurs de l'État"


def test_query_from_strategy_fails_loud_when_absent() -> None:
    source = Source(id="x", raw={"discovery": {"strategy": "no query here"}})
    with pytest.raises(spike.SpikeAbort):
        spike.query_from_strategy(source)


def test_select_csv_resource_picks_largest_not_annex() -> None:
    dataset = {
        "title": "decp",
        "resources": [
            {"format": "csv", "url": "annex", "filesize": 566787},
            {"format": "csv", "url": "main", "filesize": 80000000},
            {"format": "json", "url": "json", "filesize": 999999999},
        ],
    }
    assert spike.select_csv_resource(dataset)["url"] == "main"


def test_select_csv_resource_fails_loud_without_csv() -> None:
    with pytest.raises(spike.SpikeAbort):
        spike.select_csv_resource({"title": "x", "resources": [{"format": "json", "url": "j"}]})


def test_download_head_truncates_on_newline(respx_mock) -> None:  # type: ignore[no-untyped-def]
    body = b"col\n" + b"".join(b"%09drow\n" % i for i in range(50))  # ~450 bytes
    respx_mock.get("https://x/decp").mock(return_value=httpx.Response(200, content=body))
    with httpx.Client() as client:
        data, truncated = spike.download_head(client, "https://x/decp", 100)
    assert truncated is True
    assert len(data) <= 100
    assert data.endswith(b"row")  # dangling partial line was dropped


def test_ensure_utf8_transcodes_cp1252() -> None:
    raw = "Société;180089013".encode("cp1252")
    out, encoding = spike.ensure_utf8(raw)
    assert encoding == "cp1252"
    assert out.decode("utf-8") == "Société;180089013"


# --------------------------------------------------------------------------- #
# End-to-end live pipeline (mocked HTTP)
# --------------------------------------------------------------------------- #
@pytest.fixture
def wire_routes(load_fixture, respx_mock):  # type: ignore[no-untyped-def]
    """Register every HTTP route the live run touches, keyed on the real registry queries."""
    op_query = spike.query_from_strategy(get_source("operateurs_etat"))
    decp_query = spike.query_from_strategy(get_source("decp_commande_publique"))

    respx_mock.get(DATASETS_URL, params={"q": op_query, "page_size": "20"}).mock(
        return_value=httpx.Response(200, content=load_fixture("operateurs_search.json"))
    )
    respx_mock.get(DATASETS_URL, params={"q": decp_query, "page_size": "20"}).mock(
        return_value=httpx.Response(200, content=load_fixture("decp_search.json"))
    )
    respx_mock.get("https://www.data.gouv.fr/fr/datasets/r/op-2025-csv").mock(
        return_value=httpx.Response(200, content=load_fixture("operateurs.csv"))
    )
    respx_mock.get("https://static.data.gouv.fr/resources/decp/decp-main-csv").mock(
        return_value=httpx.Response(200, content=load_fixture("decp.csv"))
    )
    # DECP's registry schema ref points at the portal root (an HTML page, not a TableSchema):
    # resolve_schema must raise SchemaResolutionError, which the spike treats as skip-with-warning.
    respx_mock.get("https://schema.data.gouv.fr/").mock(
        return_value=httpx.Response(200, text="<html>schema portal</html>")
    )
    return respx_mock


def test_run_live_end_to_end(tmp_path, wire_routes) -> None:  # type: ignore[no-untyped-def]
    summary = spike.run_live(
        api_base=API_BASE,
        limit=20,
        max_resource_mb=50,
        snapshot_root=tmp_path / "snapshots",
        out_dir=tmp_path / "out",
    )

    # Discovery resolved the latest millésime with no hardcoded slug.
    assert "2025" in summary["operators"]["dataset"]["title"]
    # The PRIMARY (largest) CSV was chosen — not the small annex.
    assert summary["decp"]["resource_url"].endswith("/decp-main-csv")

    # SIREN coverage: 3 of 4 operators carry a SIREN.
    assert summary["operators"]["siren_column"] == "siren"
    assert summary["operators"]["coverage"] == pytest.approx(0.75)

    # Match rates (3 operator SIRENs vs the DECP sample):
    #   buyers   = CNRS + France Travail        -> 2/3
    #   suppliers= BnF (appears as titulaire)    -> 1/3
    #   either   = all three                      -> 3/3
    assert summary["match_rate"]["buyers"] == pytest.approx(2 / 3)
    assert summary["match_rate"]["suppliers"] == pytest.approx(1 / 3)
    assert summary["match_rate"]["either"] == pytest.approx(1.0)

    assert summary["verdict"] == "GO"
    assert summary["exit_ok"] is True

    # DECP validation gracefully skipped (misconfigured schema ref), not a hard failure.
    assert "skipped" in summary["decp"]["validation"].lower()

    # Raw extracts were snapshotted with a pointer, under the injected root.
    for source_id in ("operateurs_etat", "decp_commande_publique"):
        assert (tmp_path / "snapshots" / source_id / "latest.json").is_file()

    # The machine summary was recorded.
    assert (tmp_path / "out" / "phase0_live_summary.json").is_file()


def test_verdict_conditional_go_when_operators_lack_siren() -> None:
    verdict, exit_ok, interpretation = spike._verdict(
        0.0, 0.0, op_siren_column=None, decp_key_count=5000
    )
    assert verdict.startswith("CONDITIONAL GO")
    assert exit_ok is False
    assert "crosswalk" in interpretation.lower()
