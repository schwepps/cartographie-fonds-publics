"""Offline transform tests for DECP (FSC-31 contracts + FSC-39 delegates edges).

Drives ``build`` against a fixture shaped like the real consolidated-tabular extract (SIRET ids,
multi-row markets via co-titulaires + ``modification_id``/``donneesActuelles``). Asserts the
accuracy guarantees the source verification flagged: SIRET→SIREN reduction, current-attribution
selection (amended montant counted once at its latest value), equal co-titulaire split (no
double-counting), aggregated delegates edges, delegated titulaire entities, and golden-rule-#5
accounting (unresolved parties counted + listed, never dropped).
"""

from __future__ import annotations

from pathlib import Path

from core.crosswalk import Crosswalk
from core.models import Level, Nature
from ingestion.tabular import parse_csv_bytes
from ingestion.transforms import TransformResult, get_transform
from ingestion.transforms.decp_commande_publique import build

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# Real SIRENs reduced from the fixture's SIRET ids.
_CNRS = "180089013"
_FRANCE_TRAVAIL = "130005481"
_LABO = "552081317"
_CONSEIL_RH = "402360494"
_ETUDES = "326556578"
_BTP = "779999999"


def _build(crosswalk: Crosswalk | None = None) -> TransformResult:
    headers, rows = parse_csv_bytes((FIXTURES / "decp_consolidated_sample.csv").read_bytes())
    return build(headers, rows, crosswalk=crosswalk or Crosswalk.from_entries([]))


def _edge(result: TransformResult, source: str, target: str):
    return next(
        (e for e in result.edges if e.source_siren == source and e.target_siren == target), None
    )


def test_factory_routes_the_decp_source() -> None:
    from ingestion.connectors import get_connector
    from ingestion.connectors.datagouv_api import DatagouvApiConnector
    from ingestion.registry import get_source

    # The connector is source-agnostic (datagouv_api); the curation is this transform.
    assert isinstance(get_connector(get_source("decp_commande_publique")), DatagouvApiConnector)
    assert get_transform("decp_commande_publique") is not None


def test_siret_reduces_to_siren_on_both_ends() -> None:
    result = _build()
    # A market's acheteur SIRET 18008901300012 → SIREN 180089013; titulaire likewise.
    assert _edge(result, _CNRS, _LABO) is not None


def test_amended_market_uses_current_montant_not_the_initial() -> None:
    # Market C: modification_id 0 (montant 100000, donneesActuelles=false) then 1 (150000, true).
    # The current attribution must win — the amended 150000 is counted once, not summed with 100000.
    result = _build()
    edge = _edge(result, _CNRS, _BTP)
    assert edge is not None
    assert edge.amount_eur == 150_000
    contract = next(c for c in result.contracts if c.titulaire_siren == _BTP)
    assert contract.nature is Nature.concession


def test_co_titulaires_split_montant_equally() -> None:
    # Market B: montant 840000 across two co-titulaires → 420000 each (anti-double-counting).
    result = _build()
    assert _edge(result, _FRANCE_TRAVAIL, _CONSEIL_RH).amount_eur == 420_000
    assert _edge(result, _FRANCE_TRAVAIL, _ETUDES).amount_eur == 420_000
    # Summing the edges back up reproduces the market total exactly.
    b_total = sum(e.amount_eur or 0.0 for e in result.edges if e.source_siren == _FRANCE_TRAVAIL)
    assert b_total == 840_000


def test_delegated_entities_created_for_titulaires() -> None:
    result = _build()
    assert all(e.level is Level.delegated for e in result.entities)
    by_siren = {e.siren: e for e in result.entities}
    assert by_siren.keys() == {_LABO, _CONSEIL_RH, _ETUDES, _BTP}
    assert by_siren[_LABO].name == "Fournisseur Labo SA"  # name carried from titulaire_nom
    assert by_siren[_BTP].category == "Concession"
    # No buyer (acheteur) entities are emitted — buyers are owned by other layers.
    assert _CNRS not in by_siren and _FRANCE_TRAVAIL not in by_siren


def test_unresolved_acheteur_is_counted_not_dropped() -> None:
    # Market D's acheteur id "ABC" is neither a SIREN nor a SIRET and is absent from the crosswalk.
    result = _build()
    # The contract is kept (acheteur_siren=None), but no edge can form (an Edge needs both ends).
    unresolved_contract = next(c for c in result.contracts if c.acheteur_siren is None)
    assert unresolved_contract.titulaire_siren == _LABO
    assert _edge(result, _CNRS, _LABO) is not None  # A still produced its edge
    # The party is surfaced in the report (the crosswalk backlog), never silently lost.
    assert "Acheteur étranger non résolu" in result.report["unresolved_parties"]
    assert result.report["unresolved"] == 1
    assert result.report["contracts"] == 5
    assert result.report["delegates_edges"] == 4
    assert 0.0 < result.report["resolution_rate"] < 1.0


def test_split_amount_is_exact_to_the_cent() -> None:
    from ingestion.transforms.decp_commande_publique import _split_amount

    # 100 / 3 distributes the remainder cent to the first share — sums back to exactly 100.00.
    shares = _split_amount(100.0, 3)
    assert shares == [33.34, 33.33, 33.33]
    assert round(sum(s for s in shares if s is not None), 2) == 100.0
    # Clean divisions and the None passthrough.
    assert _split_amount(840_000.0, 2) == [420_000.0, 420_000.0]
    assert _split_amount(None, 2) == [None, None]


def test_indivisible_co_titulaire_split_sums_back_exactly() -> None:
    # An end-to-end market whose montant does not divide cleanly among its co-titulaires: the
    # delegates edges must still sum back to the market total exactly (anti-double-counting holds).
    headers = [
        "uid",
        "acheteur_id",
        "titulaire_id",
        "titulaire_nom",
        "montant",
        "nature",
        "dateNotification",
        "donneesActuelles",
    ]
    sirets = ["55208131700025", "40236049400015", "32655657800019"]
    rows = [
        {
            "uid": "Z",
            "acheteur_id": "18008901300012",
            "titulaire_id": s,
            "titulaire_nom": f"Titulaire {i}",
            "montant": "100",
            "nature": "Marché",
            "dateNotification": "2026-01-01",
            "donneesActuelles": "true",
        }
        for i, s in enumerate(sirets)
    ]
    result = build(headers, rows, crosswalk=Crosswalk.from_entries([]))
    cnrs_out = [e.amount_eur or 0.0 for e in result.edges if e.source_siren == _CNRS]
    assert len(cnrs_out) == 3
    assert round(sum(cnrs_out), 2) == 100.0


def test_parse_amount_handles_us_and_french_formats() -> None:
    from ingestion.transforms.decp_commande_publique import _parse_amount

    # The rightmost of ',' / '.' is the decimal separator; the other groups thousands.
    assert _parse_amount("1234.56") == 1234.56
    assert _parse_amount("1,234.56") == 1234.56  # US
    assert _parse_amount("1.234,56") == 1234.56  # French (previously mis-parsed to 1.23456)
    assert _parse_amount("1 234,56") == 1234.56  # French with a thousands space
    assert _parse_amount("840000") == 840000.0
    assert _parse_amount("") is None
    assert _parse_amount("N/A") is None


def test_market_key_falls_back_to_acheteur_plus_id_not_titulaire() -> None:
    # With no `uid` but an internal market `id`, co-titulaires of one market must stay one market
    # (keyed acheteur+id), not split by titulaire_id. Two co-titulaire rows → one market → split.
    headers = ["acheteur_id", "id", "titulaire_id", "titulaire_nom", "montant", "nature"]
    rows = [
        {
            "acheteur_id": "18008901300012",
            "id": "M-1",
            "titulaire_id": "55208131700025",
            "titulaire_nom": "A",
            "montant": "1000",
            "nature": "Marché",
        },
        {
            "acheteur_id": "18008901300012",
            "id": "M-1",
            "titulaire_id": "40236049400015",
            "titulaire_nom": "B",
            "montant": "1000",
            "nature": "Marché",
        },
    ]
    result = build(headers, rows, crosswalk=Crosswalk.from_entries([]))
    assert result.report["markets"] == 1  # grouped by acheteur+id, not split into two
    cnrs_out = [e.amount_eur or 0.0 for e in result.edges if e.source_siren == _CNRS]
    assert sorted(cnrs_out) == [500.0, 500.0]  # 1000 split equally between the two co-titulaires


def test_co_titulaire_split_is_order_independent() -> None:
    # The remainder cent is assigned by sorted titulaire id, so per-supplier amounts are identical
    # regardless of upstream row order (100 / 3, the indivisible case).
    headers = ["uid", "acheteur_id", "titulaire_id", "montant", "nature"]
    sirets = ["55208131700025", "40236049400015", "32655657800019"]

    def amounts_for(order: list[str]) -> dict[str, float]:
        rows = [
            {
                "uid": "Z",
                "acheteur_id": "18008901300012",
                "titulaire_id": s,
                "montant": "100",
                "nature": "Marché",
            }
            for s in order
        ]
        result = build(headers, rows, crosswalk=Crosswalk.from_entries([]))
        return {e.target_siren: (e.amount_eur or 0.0) for e in result.edges}

    assert amounts_for(sirets) == amounts_for(list(reversed(sirets)))


def test_missing_required_column_fails_loud() -> None:
    # If a column the curation depends on (here montant) drifts away, the transform must fail loud
    # rather than silently produce amount-less contracts (golden rule #3).
    import pytest

    headers = ["uid", "acheteur_id", "titulaire_id", "nature"]
    with pytest.raises(ValueError, match="montant"):
        build(headers, [], crosswalk=Crosswalk.from_entries([]))


def test_all_input_rows_accounted_for() -> None:
    result = _build()
    # 6 rows → 4 markets (B has 2 co-titulaire rows, C has 2 amendment rows) → 5 contracts.
    assert result.report["markets"] == 4
    assert len(result.contracts) == 5
