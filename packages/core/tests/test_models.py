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
    MentionType,
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


def test_attribution_carries_enriched_fields():
    # FSC-27: a mandate links to a real legal reference + a registry provenance.
    a = Attribution(
        entity_siren="110044013",
        legal_ref="Décret n° 2025-1021 du 29 octobre 2025",
        txt="Compétence ESR",
        source_url="https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052457282",
        provenance="legifrance_attributions",
    )
    assert a.entity_siren == "110044013"
    assert a.source_url.startswith("https://")
    assert a.provenance == "legifrance_attributions"


def test_mention_carries_enriched_fields_and_type_enum():
    # FSC-62: an oversight mention carries date/type/url/provenance/licence; type is a StrEnum.
    m = Mention(
        entity_siren="180089013",
        report_ref="Le CNRS",
        report_date="2025-03-25",
        mention_type=MentionType.rapport,
        url="https://www.ccomptes.fr/fr/publications/le-cnrs",
        note="Trésorerie pléthorique",
        provenance="cour_des_comptes",
        license="Licence Ouverte 2.0",
    )
    assert m.mention_type == "rapport"  # StrEnum round-trips to the SQL CHECK value
    assert m.url.startswith("https://")
    assert m.license == "Licence Ouverte 2.0"
    assert Mention().mention_type is None  # nullable


def test_mention_rejects_invalid_type():
    with pytest.raises(ValidationError):
        Mention(report_ref="X", mention_type="avis")


def test_source_urls_must_be_http_s_at_the_model_boundary():
    # Golden rule #10: curated links are http(s) or absent (no javascript:/data:).
    assert Attribution(source_url=None).source_url is None
    assert Mention(url="").url is None  # empty normalises to None
    with pytest.raises(ValidationError):
        Attribution(source_url="javascript:alert(1)")
    with pytest.raises(ValidationError):
        Mention(url="data:text/html,x")


def test_enum_vocabulary_matches_sql_check_constraints():
    # Pins the frozen contract: these value sets must equal the CHECK constraints in
    # supabase/migrations/0001_init.sql (mention_type: 0008). A typo here or there fails loud.
    assert {n.value for n in Level} == {"state", "local", "social", "delegated"}
    assert {t.value for t in EdgeType} == {"tutelle", "participation", "funds", "delegates"}
    assert {n.value for n in Nature} == {"marche", "concession"}
    assert {m.value for m in MentionType} == {"rapport", "recommandation"}


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
