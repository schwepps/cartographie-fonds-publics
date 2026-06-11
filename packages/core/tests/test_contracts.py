"""Tests for SIRET→SIREN reduction and the shared contract→graph derivation (FSC-31/FSC-39)."""

from core.contracts import aggregate_delegates_edges, delegated_entities
from core.models import Contract, EdgeType, Level, Nature
from core.resolve import siren_from_identifier


def test_siren_from_identifier_reduces_siret_and_keeps_siren():
    # A 14-digit SIRET reduces to its 9-digit SIREN; a clean SIREN passes through.
    assert siren_from_identifier("18008901300012") == "180089013"
    assert siren_from_identifier("180 089 013 00012") == "180089013"
    assert siren_from_identifier("180089013") == "180089013"
    assert siren_from_identifier("180 089 013") == "180089013"


def test_siren_from_identifier_never_guesses():
    # Neither a 9- nor 14-digit number → None (foreign/malformed/missing). Never fabricated.
    assert siren_from_identifier("12345") is None
    assert siren_from_identifier("XYZ") is None
    assert siren_from_identifier("") is None
    assert siren_from_identifier(None) is None


def _contract(acheteur, titulaire, montant, nature, exercice=2026):
    return Contract(
        acheteur_siren=acheteur,
        titulaire_siren=titulaire,
        montant_eur=montant,
        nature=Nature(nature),
        exercice=exercice,
    )


def test_aggregate_delegates_edges_sums_per_pair_and_exercice():
    contracts = [
        _contract("180089013", "552081317", 1_000_000, "marche"),
        _contract("180089013", "552081317", 250_000, "marche"),  # same pair+year → summed
        _contract("180089013", "326556578", 85_000, "marche"),
        _contract("180089013", "552081317", 500_000, "marche", exercice=2025),  # other year → split
    ]
    edges = aggregate_delegates_edges(contracts, provenance="decp_commande_publique")

    # 3 distinct (acheteur, titulaire, exercice) keys; the duplicate pair collapsed, amount summed.
    assert len(edges) == 3
    assert all(e.type is EdgeType.delegates for e in edges)
    assert all(e.provenance == "decp_commande_publique" for e in edges)
    summed = next(e for e in edges if e.target_siren == "552081317" and e.exercice == 2026)
    assert summed.amount_eur == 1_250_000


def test_aggregate_delegates_edges_unknown_amount_is_none_not_zero():
    # A pair whose every contract has an unknown montant yields an edge with amount_eur=None
    # (unknown ≠ zero), never a misleading 0.0 — but the delegation edge still exists.
    contracts = [
        Contract(acheteur_siren="180089013", titulaire_siren="552081317", montant_eur=None),
        Contract(acheteur_siren="180089013", titulaire_siren="552081317", montant_eur=None),
    ]
    edges = aggregate_delegates_edges(contracts)
    assert len(edges) == 1
    assert edges[0].amount_eur is None
    # A pair with a mix of known + unknown sums only the known amounts.
    mixed = [
        Contract(acheteur_siren="180089013", titulaire_siren="326556578", montant_eur=100.0),
        Contract(acheteur_siren="180089013", titulaire_siren="326556578", montant_eur=None),
    ]
    assert aggregate_delegates_edges(mixed)[0].amount_eur == 100.0


def test_aggregate_delegates_edges_skips_unresolved_ends():
    # An unresolved acheteur OR titulaire cannot form an edge (Edge needs both) — skipped.
    contracts = [
        Contract(acheteur_siren="180089013", titulaire_siren=None, montant_eur=10.0),
        Contract(acheteur_siren=None, titulaire_siren="552081317", montant_eur=20.0),
        _contract("180089013", "552081317", 30.0, "marche"),
    ]
    edges = aggregate_delegates_edges(contracts)
    assert len(edges) == 1
    assert edges[0].amount_eur == 30.0


def test_delegated_entities_one_per_titulaire_with_name_and_category():
    contracts = [
        _contract("180089013", "552081317", 1_000_000, "marche"),
        _contract(
            "180043016", "552081317", 2_000_000, "concession"
        ),  # same titulaire, mixed nature
        _contract("180089013", "326556578", 85_000, "marche"),
    ]
    entities = delegated_entities(
        contracts,
        names={"552081317": "Fournisseur Labo SA"},
        provenance="decp_commande_publique",
    )

    assert [e.siren for e in entities] == ["326556578", "552081317"]  # sorted, deduped
    assert all(e.level is Level.delegated for e in entities)
    labo = next(e for e in entities if e.siren == "552081317")
    assert labo.name == "Fournisseur Labo SA"
    assert labo.category == "Concession / Marché public"  # both natures, sorted
    # No name supplied → falls back to the bare SIREN (matches the UI's unresolved rendering).
    bare = next(e for e in entities if e.siren == "326556578")
    assert bare.name == "326556578"
    assert bare.category == "Marché public"
