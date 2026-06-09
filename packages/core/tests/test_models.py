import pytest
from core.models import (
    Attribution,
    BudgetFact,
    Contract,
    Edge,
    EdgeType,
    Entity,
    Level,
    Mention,
    Nature,
)
from core.resolve import match_rate, normalize_name, normalize_siren
from pydantic import ValidationError


def test_normalize_siren():
    assert normalize_siren("180 089 013") == "180089013"
    assert normalize_siren("12345") is None
    assert normalize_siren(None) is None


def test_normalize_name_folds_accents_case_and_legal_forms():
    # Accents, case, and articles/legal-form tokens all fold into one comparison key.
    assert normalize_name("Bibliothèque nationale de France") == "bibliotheque nationale france"
    assert normalize_name("BIBLIOTHEQUE NATIONALE DE FRANCE") == "bibliotheque nationale france"
    assert normalize_name("Établissement public du Louvre") == "louvre"
    assert normalize_name("  France   Travail  ") == "france travail"
    assert normalize_name(None) == ""
    assert normalize_name("") == ""


def test_normalize_name_distinguishes_substantive_names():
    # Stripping only articles/legal forms must NOT collapse genuinely different entities.
    assert normalize_name("Agence nationale de la recherche") != normalize_name(
        "Agence nationale de l'habitat"
    )


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ({"1", "2"}, {"2", "3"}, 0.5),  # partial overlap
        (set(), {"1"}, 0.0),  # empty left — guards division by zero
        ({"1"}, {"1"}, 1.0),  # full overlap
        ({"1"}, {"2"}, 0.0),  # no overlap
    ],
)
def test_match_rate(left, right, expected):
    assert match_rate(left, right) == expected


def test_entity_normalizes_and_allows_none_siren():
    e = Entity(siren="180 089 013", name="CNRS", level=Level.state)
    assert e.level == Level.state
    assert e.siren == "180089013"  # normalized on input
    assert Entity(siren=None, name="Unresolved op", level=Level.state).siren is None


def test_entity_carries_optional_provenance():
    # Provenance (the registry source id) mirrors Edge.provenance: optional, defaults None.
    assert Entity(siren=None, name="X", level=Level.state).provenance is None
    op = Entity(siren="180089013", name="CNRS", level=Level.state, provenance="operateurs_etat")
    assert op.provenance == "operateurs_etat"


def test_entity_rejects_invalid_siren():
    with pytest.raises(ValidationError):
        Entity(siren="abc123", name="Bad", level=Level.state)


def test_entity_rejects_invalid_level():
    with pytest.raises(ValidationError):
        Entity(siren=None, name="X", level="unknown_level")


def test_edge_requires_valid_sirens():
    edge = Edge(source_siren="180089013", target_siren="130025265", type=EdgeType.funds)
    assert edge.source_siren == "180089013"
    with pytest.raises(ValidationError):
        Edge(source_siren="nope", target_siren="130025265", type=EdgeType.funds)


def test_attribution_and_mention_construct():
    assert Attribution(legal_ref="L.123", txt="competence").legal_ref == "L.123"
    assert Mention(report_ref="CdC-2025", note="cited").note == "cited"


def test_enum_vocabulary_matches_sql_check_constraints():
    # Pins the frozen contract: these value sets must equal the CHECK constraints in
    # supabase/migrations/0001_init.sql. A typo here (or there) fails loud.
    assert {n.value for n in Level} == {"state", "local", "social", "delegated"}
    assert {t.value for t in EdgeType} == {"tutelle", "participation", "funds", "delegates"}
    assert {n.value for n in Nature} == {"marche", "concession"}


def test_contract_nature_enum():
    c = Contract(acheteur_siren="180089013", titulaire_siren=None, nature=Nature.marche)
    assert c.nature == Nature.marche
    assert c.nature == "marche"  # StrEnum round-trips to the SQL CHECK value
    assert Contract(acheteur_siren=None, titulaire_siren=None).nature is None  # nullable


def test_contract_rejects_invalid_nature():
    with pytest.raises(ValidationError):
        Contract(acheteur_siren=None, titulaire_siren=None, nature="bail")


def test_budget_fact_requires_exercice_and_defaults_executed():
    fact = BudgetFact(entity_siren="180089013", exercice=2025)
    assert fact.exercice == 2025
    assert fact.executed is False  # voted, not executed, by default
    with pytest.raises(ValidationError):
        BudgetFact(entity_siren="180089013")  # exercice is required (NOT NULL in SQL)


def test_models_forbid_unknown_fields():
    with pytest.raises(ValidationError):
        Entity(siren=None, name="X", level=Level.state, foo="stray")
