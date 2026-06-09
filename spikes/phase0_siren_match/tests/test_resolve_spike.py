"""Offline tests for the Phase-0.5 operator name->SIREN resolution spike (FSC-48).

The data.gouv.fr catalog, the resource downloads, and every recherche-entreprises lookup are
replayed from recorded fixtures via respx — the run is fully deterministic and offline.
"""

from __future__ import annotations

import httpx
import pytest
import resolve_spike
import spike
from ingestion.registry import get_source

API_BASE = "https://www.data.gouv.fr/api/1"
DATASETS_URL = f"{API_BASE}/datasets/"
RECHERCHE_URL = "https://recherche-entreprises.api.gouv.fr/search"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Drop the API rate-limit sleep so the offline suite stays instant."""
    monkeypatch.setattr(resolve_spike, "RATE_LIMIT_SLEEP", 0)


# --------------------------------------------------------------------------- #
# classify_operator — the 3 ambiguity tiers (no network)
# --------------------------------------------------------------------------- #
def _candidate(siren: str, name: str, *, public: bool = True, nature: str = "7389") -> dict:
    return {
        "siren": siren,
        "nom_complet": name,
        "nature_juridique": nature,
        "complements": {"est_administration": public},
    }


def test_classify_unique_exact_match() -> None:
    record = resolve_spike.classify_operator(
        "Centre national de la recherche scientifique",
        "MESR",
        [_candidate("180089013", "CENTRE NATIONAL DE LA RECHERCHE SCIENTIFIQUE")],
    )
    assert record["tier"] == "unique"
    assert record["chosen_siren"] == "180089013"


def test_classify_none_when_no_exact_name() -> None:
    # A near-miss name must NOT be auto-accepted (golden rule #5 — never guess).
    record = resolve_spike.classify_operator(
        "Agence nationale de la recherche", "MESR", [_candidate("999999999", "AGENCE DE L'EAU")]
    )
    assert record["tier"] == "none"
    assert record["chosen_siren"] is None
    assert record["top_match_ratio"] < 1.0  # described for the backlog, not accepted


def test_classify_multiple_when_two_public_namesakes() -> None:
    record = resolve_spike.classify_operator(
        "Opérateur ambigu",
        "MEF",
        [_candidate("111222333", "OPERATEUR AMBIGU"), _candidate("444555666", "OPERATEUR AMBIGU")],
    )
    assert record["tier"] == "multiple"
    assert record["chosen_siren"] is None  # ambiguity is routed to the crosswalk, never guessed
    assert sorted(record["candidate_sirens"]) == ["111222333", "444555666"]


def test_classify_soft_filter_breaks_tie_to_single_public() -> None:
    record = resolve_spike.classify_operator(
        "Bibliothèque nationale de France",
        "MC",
        [
            _candidate(
                "552081317", "BIBLIOTHEQUE NATIONALE DE FRANCE", public=False, nature="5499"
            ),
            _candidate("180046112", "BIBLIOTHEQUE NATIONALE DE FRANCE"),
        ],
    )
    assert record["tier"] == "unique"
    assert record["chosen_siren"] == "180046112"  # public-sector soft filter resolved the tie


def test_acronym_prefix_resolves_to_full_legal_name() -> None:
    # "IGN - Institut..." must match SIRENE's bare "INSTITUT..." — a stripped formatting prefix,
    # still accepted only on EXACT normalized equality of the cleaned name.
    record = resolve_spike.classify_operator(
        "IGN - Institut national de l'information géographique et forestière",
        "MTE",
        [_candidate("180066043", "INSTITUT NATIONAL DE L'INFORMATION GEOGRAPHIQUE ET FORESTIERE")],
    )
    assert record["tier"] == "unique"
    assert record["chosen_siren"] == "180066043"


def test_name_variants_keeps_hyphenated_single_names_intact() -> None:
    # Spaces are required around the dash, so a hyphenated name is never split into a stray token.
    assert resolve_spike._name_variants("Météo-France") == ["Météo-France"]
    assert "Institut de recherche pour le développement" in resolve_spike._name_variants(
        "IRD - Institut de recherche pour le développement"
    )


def test_resolve_verdict_thresholds() -> None:
    proceed, ok, _ = resolve_spike._resolve_verdict(0.6, 4)
    assert proceed == "PROCEED TO PHASE 1" and ok is True
    curate, ok, _ = resolve_spike._resolve_verdict(0.2, 9)
    assert curate.startswith("CURATE-FIRST") and "9 operators" in curate and ok is False


# --------------------------------------------------------------------------- #
# Offline sample mode (`make spike-resolve`)
# --------------------------------------------------------------------------- #
def test_run_sample_reports_tiers_and_appearance(tmp_path) -> None:  # type: ignore[no-untyped-def]
    summary = resolve_spike.run_sample(out_dir=tmp_path)

    assert summary["tiers"] == {"unique": 3, "multiple": 1, "none": 1}
    assert summary["resolution_rate"] == pytest.approx(0.6)
    assert summary["manual_backlog"] == 2
    assert summary["decp_appearance_rate"] == pytest.approx(1.0)  # all 3 resolved appear in DECP
    assert summary["exit_ok"] is True
    assert (tmp_path / "operator_resolution.csv").is_file()
    assert (tmp_path / "phase0_5_resolution_summary.json").is_file()


# --------------------------------------------------------------------------- #
# End-to-end live pipeline (mocked HTTP)
# --------------------------------------------------------------------------- #
@pytest.fixture
def wire_routes(load_fixture, respx_mock):  # type: ignore[no-untyped-def]
    """Register every HTTP route the live resolution run touches."""
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
    respx_mock.get("https://schema.data.gouv.fr/").mock(
        return_value=httpx.Response(200, text="<html>schema portal</html>")
    )

    # One recherche-entreprises route per operator in operateurs.csv (keyed on the query name).
    for name, fixture in (
        ("Centre national de la recherche scientifique", "recherche_cnrs.json"),
        ("France Travail", "recherche_france_travail.json"),
        ("Bibliothèque nationale de France", "recherche_bnf.json"),
        ("Agence sans SIREN", "recherche_agence_sans_siren.json"),
    ):
        respx_mock.get(RECHERCHE_URL, params={"q": name, "page": "1", "per_page": "10"}).mock(
            return_value=httpx.Response(200, content=load_fixture(fixture))
        )
    return respx_mock


def test_run_live_end_to_end(tmp_path, wire_routes) -> None:  # type: ignore[no-untyped-def]
    summary = resolve_spike.run_live(
        api_base=API_BASE,
        limit=20,
        max_resource_mb=50,
        snapshot_root=tmp_path / "snapshots",
        out_dir=tmp_path / "out",
    )

    # Operator-name + tutelle columns detected from the registry-discovered CSV (no hardcoding).
    assert summary["denomination_column"] == "operateur"
    assert summary["tutelle_column"] == "tutelle"
    assert summary["resolver_base_url"] == RECHERCHE_URL

    # 3 unique (CNRS, France Travail, BnF-via-soft-filter), 1 none (Agence sans SIREN).
    assert summary["tiers"] == {"unique": 3, "multiple": 0, "none": 1}
    assert summary["resolution_rate"] == pytest.approx(0.75)
    assert summary["manual_backlog"] == 1

    # Closes FSC-19's structural 0%: all 3 resolved SIRENs appear in the DECP sample.
    assert summary["decp_appearance_rate"] == pytest.approx(1.0)
    assert summary["verdict"] == "PROCEED TO PHASE 1"
    assert summary["exit_ok"] is True

    # Operators were snapshotted, and the crosswalk + summary artifacts were written.
    assert (tmp_path / "snapshots" / "operateurs_etat" / "latest.json").is_file()
    assert (tmp_path / "out" / "operator_resolution.csv").is_file()
    assert (tmp_path / "out" / "phase0_5_resolution_summary.json").is_file()
