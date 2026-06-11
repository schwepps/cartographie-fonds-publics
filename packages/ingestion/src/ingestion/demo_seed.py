"""Build the ILLUSTRATIVE demo seed (FSC-50…53): a design-scale dev/preview dataset.

Unlike the real curated seed (:mod:`ingestion.seed`, FSC-24), this dataset is **illustrative**
(« exemple »): the operators, funding flows and amounts are a plausible ~70-entity slice ported
from the delivered design reference (``design/js/data.js``), so the redesigned screens render rich
graphs, flows and figures in **local dev and Vercel previews** *before* the funding-flow ingestion
(FSC-39 delegates / FSC-33 participation) lands. **DEV/PREVIEW ONLY — never load into production.**

Honesty conventions (golden rule #8/#10):

* Euro amounts are illustrative unless tied to a published figure — the **MESR / MIRES budget rows
  are the real PLF 2025 voté totals** (reused from the real seed). The UI flags illustrative
  figures with « exemple ».
* "Unresolved" entities (« SIREN non résolu ») are modelled the real way: two DECP titulaires
  (329200521, 326556578) are referenced by ``delegates`` edges + contracts but have **no entity
  row**, so the UI renders them as unresolved placeholders.

``build_demo()`` constructs frozen domain models (validated for free); ``render_sql()`` serialises
them deterministically to ``supabase/demo_seed.sql`` (loaded by local ``supabase db reset`` and by
``make demo-seed``). A golden test (``tests/test_demo_seed.py``) fails loud on drift.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from core.models import BudgetFact, Contract, Edge, EdgeType, Entity, Level, Nature, Nomenclature

from .sql_render import (
    BUDGET_COLUMNS,
    CONTRACT_COLUMNS,
    EDGE_COLUMNS,
    ENTITY_COLUMNS,
    render_insert,
)

# Registry source ids stamped per layer (same ids the real transforms use, so the UI resolves them
# to real source names; the whole slice is dev/preview-only).
# Registry source ids (must match data/registry/sources-registry.yaml so the provenance UI resolves
# them to real source names).
_P_OPERATORS = "operateurs_etat"
_P_BUDGET = "budget_plf_lfi"
_P_DECP = "decp_commande_publique"
_P_OFGL = "finances_locales_ofgl"
_P_SECU = "comptes_sociaux"
_P_EPL = "epl_sem_spl"

_MINISTRY_CATEGORY = "ministère"

_DEFAULT_DEMO_SQL_PATH = Path(__file__).resolve().parents[4] / "supabase" / "demo_seed.sql"
DEMO_SQL_PATH = Path(os.environ.get("CFP_DEMO_SEED_SQL_PATH", _DEFAULT_DEMO_SQL_PATH))

# --------------------------------------------------------------------------- #
# Illustrative data — ported from design/js/data.js (French level keys mapped to the DB's
# state/local/social/delegated). (siren, name, category) tuples; parent set per cluster.
# --------------------------------------------------------------------------- #
_MINISTRIES: tuple[tuple[str, str], ...] = (
    ("110046018", "Ministère de la Culture"),
    ("110044013", "Ministère de l’Enseignement supérieur et de la Recherche"),
    ("110000072", "Ministère du Travail et des Solidarités"),
)

# State operators by tutelle ministry: parent -> [(siren, name, category)].
_STATE_OPERATORS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "110046018": (
        ("180046252", "Bibliothèque nationale de France", "EPA"),
        ("180043016", "Musée du Louvre", "EPA"),
        ("775670387", "Centre Pompidou", "EPA"),
        ("180046443", "Château de Versailles", "EPA"),
        ("784359069", "Opéra national de Paris", "EPIC"),
        ("180046021", "Centre national du cinéma et de l’image animée", "EPA"),
        ("301945269", "Institut national de l’audiovisuel", "EPIC"),
        ("180046096", "Centre des monuments nationaux", "EPA"),
        ("130018299", "Mobilier national", "Service"),
        ("775690703", "Cité de la musique — Philharmonie de Paris", "Association"),
        ("400000001", "Réunion des musées nationaux — Grand Palais", "EPIC"),
        ("400000002", "Institut national d’histoire de l’art", "EPA"),
        ("400000003", "Cité de l’architecture et du patrimoine", "EPIC"),
        ("400000004", "Centre national des arts plastiques", "EPA"),
        ("400000005", "Musée d’Orsay et de l’Orangerie", "EPA"),
        ("400000006", "Musée du quai Branly — Jacques Chirac", "EPA"),
        ("400000007", "Comédie-Française", "EPIC"),
    ),
    "110044013": (
        ("180089013", "Centre national de la recherche scientifique", "EPST"),
        ("180036048", "Institut national de la santé et de la recherche médicale", "EPST"),
        (
            "180070039",
            "Institut national de recherche pour l’agriculture, l’alimentation et l’environnement",
            "EPST",
        ),
        (
            "180089740",
            "Institut national de recherche en sciences et technologies du numérique",
            "EPST",
        ),
        ("775685019", "Commissariat à l’énergie atomique et aux énergies alternatives", "EPIC"),
        ("775665912", "Centre national d’études spatiales", "EPIC"),
        ("130015332", "Agence nationale de la recherche", "EPA"),
        ("197517177", "Université Paris-Saclay", "EPSCP"),
        ("130031023", "Université PSL", "EPSCP"),
        ("193100339", "Sorbonne Université", "EPSCP"),
        ("775723876", "Centre national des œuvres universitaires et scolaires", "EPA"),
        ("180020010", "Institut de recherche pour le développement", "EPST"),
        ("400000008", "École nationale supérieure des Mines", "EPSCP"),
        ("400000009", "Institut Polytechnique de Paris", "EPSCP"),
        ("400000010", "Université Grenoble-Alpes", "EPSCP"),
        ("400000011", "Université de Strasbourg", "EPSCP"),
        ("400000012", "Université d’Aix-Marseille", "EPSCP"),
        ("400000013", "Conservatoire national des arts et métiers", "EPSCP"),
        ("400000014", "Institut national d’études démographiques", "EPST"),
        ("400000015", "Office national d’études aérospatiales", "EPIC"),
        ("400000016", "Bureau de recherches géologiques et minières", "EPIC"),
        ("400000017", "Institut français de recherche pour l’exploitation de la mer", "EPIC"),
    ),
    "110000072": (
        ("130005481", "France Travail", "EPA"),
        ("824084658", "Agence nationale pour la formation professionnelle des adultes", "EPIC"),
        ("130025265", "France compétences", "EPA"),
        ("180092009", "Agence nationale pour l’amélioration des conditions de travail", "EPA"),
        ("400000018", "Agence nationale de santé publique", "EPA"),
        (
            "400000019",
            "Institut national du travail, de l’emploi et de la formation professionnelle",
            "EPA",
        ),
    ),
}

# (siren, name, category) — no parent; provenance per group.
_SOCIAL: tuple[tuple[str, str, str], ...] = (
    ("180035024", "Caisse nationale de l’assurance maladie", "Caisse nationale"),
    ("775678633", "Caisse nationale d’assurance vieillesse", "Caisse nationale"),
    ("180020075", "Caisse nationale des allocations familiales", "Caisse nationale"),
    ("180035040", "Urssaf Caisse nationale", "Caisse nationale"),
    ("301846688", "Agirc-Arrco", "Régime paritaire"),
    ("180090094", "Caisse centrale de la Mutualité sociale agricole", "Régime"),
)
_LOCAL: tuple[tuple[str, str, str], ...] = (
    ("237500139", "Région Île-de-France", "Région"),
    ("200053781", "Métropole de Lyon", "Métropole"),
    ("217500016", "Ville de Paris", "Commune"),
    ("225900019", "Département du Nord", "Département"),
    ("243300316", "Bordeaux Métropole", "Métropole"),
    ("200054807", "Région Auvergne-Rhône-Alpes", "Région"),
)
_DELEGATED: tuple[tuple[str, str, str], ...] = (
    ("552081317", "Groupe Demeter (BTP patrimoine)", "Concession"),
    ("402360441", "Société Helios Numérique", "Marché public"),
    ("552100554", "Société Restalia (restauration collective)", "Délégation de service public"),
    ("440048882", "Atlas Édition scientifique", "Marché public"),
    ("552032534", "EnerGaïa Énergies", "Concession"),
)
# Local public companies (SEM/SPL) + their public shareholder — the local delegated link (FSC-33).
# (company_siren, company_name, category, holder_siren). Holders are local entities in `_LOCAL`.
_SEM_SPL: tuple[tuple[str, str, str, str], ...] = (
    ("552032708", "SEM Lyon Confluence", "SEM", "200053781"),
    ("529000019", "SPL Paris Seine Ouest Aménagement", "SPL", "217500016"),
)

# funds / participation / delegates flows: (source, target, type, amount_eur, exercice, provenance).
_FLOWS: tuple[tuple[str, str, str, float, int, str], ...] = (
    # State subventions pour charges de service public (illustrative).
    ("110046018", "180046252", "funds", 198_000_000, 2025, _P_BUDGET),
    ("110046018", "180043016", "funds", 99_000_000, 2025, _P_BUDGET),
    ("110046018", "180046021", "funds", 712_000_000, 2025, _P_BUDGET),
    ("110046018", "784359069", "funds", 95_000_000, 2025, _P_BUDGET),
    ("110046018", "180046096", "funds", 102_000_000, 2025, _P_BUDGET),
    ("110044013", "180089013", "funds", 2_950_000_000, 2025, _P_BUDGET),
    ("110044013", "180036048", "funds", 720_000_000, 2025, _P_BUDGET),
    ("110044013", "775685019", "funds", 1_750_000_000, 2025, _P_BUDGET),
    ("110044013", "775665912", "funds", 2_100_000_000, 2025, _P_BUDGET),
    ("110044013", "130015332", "funds", 1_100_000_000, 2025, _P_BUDGET),
    ("110044013", "775723876", "funds", 2_700_000_000, 2025, _P_BUDGET),
    ("110044013", "180070039", "funds", 690_000_000, 2025, _P_BUDGET),
    ("110000072", "130005481", "funds", 1_350_000_000, 2025, _P_BUDGET),
    ("110000072", "824084658", "funds", 110_000_000, 2025, _P_BUDGET),
    ("110000072", "130025265", "funds", 1_600_000_000, 2025, _P_BUDGET),
    # Local cofinancement (illustrative).
    ("237500139", "193100339", "funds", 64_000_000, 2024, _P_OFGL),
    ("237500139", "197517177", "funds", 88_000_000, 2024, _P_OFGL),
    ("200053781", "130031023", "funds", 12_000_000, 2024, _P_OFGL),
    ("217500016", "775670387", "funds", 9_000_000, 2024, _P_OFGL),
    ("217500016", "784359069", "funds", 7_000_000, 2024, _P_OFGL),
    # Social participation (illustrative).
    ("180035024", "180036048", "participation", 240_000_000, 2024, _P_SECU),
    ("301846688", "130005481", "participation", 4_000_000_000, 2024, _P_SECU),
    # Delegates (marché / DSP) — two point at unresolved titulaires (no entity row).
    ("180089013", "329200521", "delegates", 1_800_000, 2026, _P_DECP),
    ("180089013", "326556578", "delegates", 85_000, 2026, _P_DECP),
    ("180046252", "440048882", "delegates", 4_200_000, 2026, _P_DECP),
    ("180043016", "552081317", "delegates", 48_000_000, 2026, _P_DECP),
    ("784359069", "552100554", "delegates", 22_000_000, 2026, _P_DECP),
    ("775685019", "552032534", "delegates", 64_000_000, 2026, _P_DECP),
    ("130005481", "402360441", "delegates", 19_000_000, 2026, _P_DECP),
    ("180046096", "552081317", "delegates", 16_000_000, 2026, _P_DECP),
)

# Budget facts (mission/programme grain). MESR/MIRES 2025 voté = real PLF figures (as in seed.py);
# the 2024 executed rows + other missions are illustrative for the trend spark / budget bars.
_BUDGET: tuple[tuple[str, int, str, str, int, int, bool], ...] = (
    (
        "110044013",
        2025,
        "MIRES",
        "150 — Formations supérieures et recherche universitaire",
        15_217_000_000,
        15_279_000_000,
        False,
    ),
    (
        "110044013",
        2025,
        "MIRES",
        "172 — Recherches scientifiques et technologiques pluridisciplinaires",
        8_259_807_441,
        8_701_105_312,
        False,
    ),
    ("110044013", 2025, "MIRES", "193 — Recherche spatiale", 2_100_000_000, 2_100_000_000, False),
    (
        "110044013",
        2024,
        "MIRES",
        "150 — Formations supérieures et recherche universitaire",
        14_690_000_000,
        14_710_000_000,
        True,
    ),
    (
        "110044013",
        2024,
        "MIRES",
        "172 — Recherches scientifiques et technologiques pluridisciplinaires",
        7_980_000_000,
        8_120_000_000,
        True,
    ),
    ("110046018", 2025, "Culture", "175 — Patrimoines", 1_240_000_000, 1_190_000_000, False),
    ("110046018", 2025, "Culture", "131 — Création", 1_010_000_000, 990_000_000, False),
    (
        "110046018",
        2025,
        "Culture",
        "224 — Soutien aux politiques culturelles",
        780_000_000,
        760_000_000,
        False,
    ),
    (
        "110000072",
        2025,
        "Travail et emploi",
        "102 — Accès et retour à l’emploi",
        7_100_000_000,
        6_980_000_000,
        False,
    ),
    (
        "110000072",
        2025,
        "Travail et emploi",
        "103 — Accompagnement des mutations économiques",
        8_800_000_000,
        8_400_000_000,
        False,
    ),
)

# Local budget facts (M57 universe): OFGL expenditure agrégats for a few collectivités, so a local
# entity's Fiche shows a budget and the anti-double-counting note has a genuine State↔local mix to
# guard (FSC-32/FSC-42). Illustrative amounts (« exemple »); (siren, exercice, agrégat, montant_cp).
_LOCAL_BUDGET: tuple[tuple[str, int, str, int], ...] = (
    ("237500139", 2023, "Dépenses de fonctionnement", 3_400_000_000),
    ("237500139", 2023, "Dépenses d’investissement", 2_100_000_000),
    ("200053781", 2023, "Dépenses de fonctionnement", 2_300_000_000),
    ("200053781", 2023, "Dépenses d’investissement", 900_000_000),
    ("217500016", 2023, "Dépenses de fonctionnement", 8_000_000_000),
    ("217500016", 2023, "Dépenses d’investissement", 1_500_000_000),
)

# Contracts (DECP) — the schema has no `objet` column, so it is dropped.
_CONTRACTS: tuple[tuple[str, str, float, str, int], ...] = (
    ("180089013", "329200521", 1_800_000, "marche", 2026),
    ("180089013", "326556578", 84_925.39, "marche", 2026),
    ("180043016", "552081317", 48_000_000, "marche", 2026),
    ("784359069", "552100554", 22_000_000, "concession", 2026),
    ("775685019", "552032534", 64_000_000, "concession", 2026),
    ("180046252", "440048882", 4_200_000, "marche", 2026),
)


@dataclass(frozen=True)
class DemoBundle:
    """The illustrative demo slice. Mirrors ``seed.SeedBundle``."""

    entities: list[Entity] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    budget_facts: list[BudgetFact] = field(default_factory=list)
    contracts: list[Contract] = field(default_factory=list)


def build_demo() -> DemoBundle:
    """Build the illustrative demo bundle (entities, tutelle + flow edges, budgets, contracts)."""
    entities: list[Entity] = []
    edges: list[Edge] = []

    for siren, name in _MINISTRIES:
        entities.append(
            Entity(
                siren=siren,
                name=name,
                level=Level.state,
                category=_MINISTRY_CATEGORY,
                provenance=_P_OPERATORS,
            )
        )
    for parent, operators in _STATE_OPERATORS.items():
        for siren, name, category in operators:
            entities.append(
                Entity(
                    siren=siren,
                    name=name,
                    level=Level.state,
                    category=category,
                    parent_siren=parent,
                    provenance=_P_OPERATORS,
                )
            )
            edges.append(
                Edge(
                    source_siren=parent,
                    target_siren=siren,
                    type=EdgeType.tutelle,
                    provenance=_P_OPERATORS,
                )
            )
    for siren, name, category in _SOCIAL:
        entities.append(
            Entity(
                siren=siren, name=name, level=Level.social, category=category, provenance=_P_SECU
            )
        )
    for siren, name, category in _LOCAL:
        entities.append(
            Entity(siren=siren, name=name, level=Level.local, category=category, provenance=_P_OFGL)
        )
    for siren, name, category in _DELEGATED:
        entities.append(
            Entity(
                siren=siren, name=name, level=Level.delegated, category=category, provenance=_P_DECP
            )
        )
    # SEM/SPL companies (delegated) + a participation edge from their public shareholder (FSC-33).
    for company, name, category, holder in _SEM_SPL:
        entities.append(
            Entity(
                siren=company,
                name=name,
                level=Level.delegated,
                category=category,
                provenance=_P_EPL,
            )
        )
        edges.append(
            Edge(
                source_siren=holder,  # the public shareholder
                target_siren=company,  # holds a stake in the SEM/SPL
                type=EdgeType.participation,
                provenance=_P_EPL,
            )
        )

    for source, target, edge_type, amount, exercice, provenance in _FLOWS:
        edges.append(
            Edge(
                source_siren=source,
                target_siren=target,
                type=EdgeType(edge_type),
                amount_eur=amount,
                exercice=exercice,
                provenance=provenance,
            )
        )

    budget_facts = [
        BudgetFact(
            entity_siren=siren,
            exercice=exercice,
            mission=mission,
            programme=programme,
            amount_ae_eur=ae,
            amount_cp_eur=cp,
            executed=executed,
            provenance=_P_BUDGET,
        )
        for siren, exercice, mission, programme, ae, cp, executed in _BUDGET
    ]
    # Local M57 expenditure facts (cash-basis: AE/CP do not apply), so a collectivité's Fiche
    # carries a budget in a *different* accounting universe from the State's LOLF credits (FSC-32).
    budget_facts += [
        BudgetFact(
            entity_siren=siren,
            exercice=exercice,
            programme=agregat,
            amount_cp_eur=cp,
            executed=True,
            nomenclature=Nomenclature.m57,
            provenance=_P_OFGL,
        )
        for siren, exercice, agregat, cp in _LOCAL_BUDGET
    ]
    contracts = [
        Contract(
            acheteur_siren=acheteur,
            titulaire_siren=titulaire,
            montant_eur=montant,
            nature=Nature(nature),
            exercice=exercice,
            provenance=_P_DECP,
        )
        for acheteur, titulaire, montant, nature, exercice in _CONTRACTS
    ]

    # Deterministic order for a stable golden file: entities by (level, siren); edges by
    # (source, target, type); budget/contracts as authored.
    entities.sort(key=lambda e: (e.level.value, e.siren or ""))
    edges.sort(key=lambda e: (e.source_siren, e.target_siren, e.type.value))
    return DemoBundle(
        entities=entities, edges=edges, budget_facts=budget_facts, contracts=contracts
    )


_SQL_HEADER = """\
-- supabase/demo_seed.sql — ILLUSTRATIVE demo seed (FSC-50…53). GENERATED, do not edit by hand:
-- regenerate with `make demo-seed` (source: packages/ingestion/src/ingestion/demo_seed.py).
--
-- A design-scale, plausible État-central + local + social + délégué slice so the redesigned
-- screens render rich graphs, flows and figures in local dev / Vercel previews before the
-- funding-flow ingestion (FSC-39/FSC-33) lands. DEV/PREVIEW ONLY — never apply to production.
--
-- Euro amounts are ILLUSTRATIVE (« exemple ») unless published: the MESR/MIRES budget rows are the
-- real PLF 2025 voté totals. Two DECP titulaires are referenced by edges/contracts with no entity
-- row, so the UI shows them as « SIREN non résolu ». Licence Ouverte / Etalab 2.0 where attributed.
"""


def render_sql(bundle: DemoBundle) -> str:
    """Serialise a :class:`DemoBundle` to a deterministic, idempotent SQL script."""
    sections = [
        _SQL_HEADER,
        "\nbegin;",
        "\n-- Idempotent: clear the curated tables, then re-insert the illustrative slice.",
        "truncate entities, edges, budget_facts, contracts, attributions, mentions "
        "restart identity cascade;",
        "\n-- Entities (illustrative operators across the four levels).",
        render_insert("entities", ENTITY_COLUMNS, list(bundle.entities)),
        "-- Edges: tutelle + illustrative funds / participation / delegates flows.",
        render_insert("edges", EDGE_COLUMNS, list(bundle.edges)),
        "-- Budget facts: MESR/MIRES real PLF totals + illustrative missions/years.",
        render_insert("budget_facts", BUDGET_COLUMNS, list(bundle.budget_facts)),
        "-- Contracts (illustrative DECP marchés / concessions).",
        render_insert("contracts", CONTRACT_COLUMNS, list(bundle.contracts)),
        "\ncommit;\n",
    ]
    return "\n".join(sections)


def emit_demo_sql(path: Path | str = DEMO_SQL_PATH) -> Path:
    """Render the demo seed and write it to ``path`` (the committed ``supabase/demo_seed.sql``)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sql(build_demo()), encoding="utf-8")
    return path
