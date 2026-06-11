"""Build the committed curated seed (FSC-24): a tiny, real, licence-attributed État-central slice.

A fresh dev DB — and every Vercel preview — must render a populated graph + entity sheet
*without* waiting on the full ingestion load (FSC-35). This module is the source of that slice:
``build_seed()`` constructs frozen-model instances (so validation against the domain model is
free) and ``render_sql()`` serializes them to a deterministic ``supabase/seed.sql``. ``make seed``
and ``supabase db reset`` load that SQL; a golden test (``tests/test_seed.py``) fails loud if the
committed SQL ever drifts from this builder.

Everything here is **real and attributed** (golden rule #10 — no invented data):

* Ministries, operators and tutelle edges are resolved from the committed crosswalk YAMLs
  (``data/crosswalk/*.yaml``) — SIRENs are *never* hardcoded in this file; we look them up by
  name, mirroring the ``operateurs_etat`` transform's anchoring (golden rule #1/#5).
* Budget facts are the real PLF 2025 voted totals for the MIRES mission (programmes 150 & 172),
  attributed to the mission's **owning ministry** (MESR — the budget holder), whose SIREN is
  resolved from the reviewed ministry reference, never hardcoded (golden rule #5). Attaching a
  programme total to the ministry that *runs* it is not the double-count golden rule #8 guards
  against — that is attributing it onward to the operators the programme funds. NOTE: the
  production ``budget_plf_lfi`` transform currently emits these facts with ``entity_siren=None``;
  populating the ministry sheet from the full load is an FSC-36 follow-up (see the PR notes).
* Contracts are real DECP rows where the CNRS is the acheteur; they also drive the seed's
  ``delegates`` edges (CNRS -> titulaire) via ``core.contracts`` (FSC-39), so the funding-flow
  views render real delegation links, queryable through ``graph_neighbors``.

Provenance + licence for every figure live in the SQL header (see ``_SQL_HEADER``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from core.contracts import DECP_PROVENANCE, aggregate_delegates_edges
from core.crosswalk import Crosswalk
from core.models import BudgetFact, Contract, Edge, EdgeType, Entity, Level, Nature
from core.resolve import normalize_name

from .crosswalk_io import load_crosswalk
from .sql_render import (
    BUDGET_COLUMNS,
    CONTRACT_COLUMNS,
    EDGE_COLUMNS,
    ENTITY_COLUMNS,
    render_insert,
)
from .transforms.operateurs_etat import MINISTRY_CATEGORY, MinistryIndex

# Registry source id stamped on every seeded entity and tutelle edge. The État-central skeleton
# (ministries, operators, tutelle) originates from the Jaune « Opérateurs de l'État » — so we use
# its real registry id, honouring `provenance`'s documented contract ("source id from the
# registry") and letting the UI resolve it to a real source name. (The whole seed slice is
# dev/preview-only and truncates the curated tables, which is what marks it as seed data.)
PROVENANCE = "operateurs_etat"

# Registry source id for the seeded budget facts (voted PLF). Matches the production
# `budget_plf_lfi` transform's SOURCE_ID so the seed and the full load stamp provenance identically.
BUDGET_PROVENANCE = "budget_plf_lfi"

# The committed artifact this builder generates. Same env-override pattern as crosswalk_io.
_DEFAULT_SEED_SQL_PATH = Path(__file__).resolve().parents[4] / "supabase" / "seed.sql"
SEED_SQL_PATH = Path(os.environ.get("CFP_SEED_SQL_PATH", _DEFAULT_SEED_SQL_PATH))

# Operators to seed: (crosswalk denomination, real juridical category). The SIREN and tutelle are
# read from the crosswalk at build time — only the curated *selection* and the category (which the
# crosswalk does not carry) live here. France Travail's INSEE category is left out rather than
# asserted wrongly.
_SEED_OPERATORS: tuple[tuple[str, str | None], ...] = (
    ("Centre national de la recherche scientifique", "EPST"),
    ("Bibliothèque nationale de France", "EPA"),
    ("France Travail", None),
)

# The MIRES mission is run by the MESR ministry, so its programme credits sit on MESR (the budget
# holder). We carry the ministry's reviewed tutelle *code* here — never its SIREN — and resolve the
# SIREN from the ministry reference at build time (golden rule #5).
_BUDGET_MISSION_OWNER_TUTELLE = "MESR"


def _seed_budget_facts(owner_siren: str) -> list[BudgetFact]:
    """Real PLF 2025 voted credits for the MIRES mission (programmes 150 & 172).

    Mission/programme grain, attributed to the mission's owning ministry (``owner_siren`` — MESR,
    resolved from the ministry reference, never hardcoded). Amounts in euros: programme 172 to the
    euro; programme 150 at the published million precision (LPR 5e annuité). Source: Sénat, rapport
    général PLF 2025 — Recherche et enseignement supérieur
    (https://www.senat.fr/rap/l24-144-324/l24-144-324_mono.html) + budget.gouv.fr PAP. Licence
    Ouverte 2.0.
    """
    # These are voted PLF credits, so they carry the State-budget source's registry id — the same
    # provenance the production `budget_plf_lfi` transform stamps (FSC-35), letting the UI attribute
    # the figures and a State-budget reload replace exactly its own facts.
    return [
        BudgetFact(
            entity_siren=owner_siren,
            exercice=2025,
            mission="MIRES",
            programme="150",
            amount_ae_eur=15_217_000_000,
            amount_cp_eur=15_279_000_000,
            executed=False,
            provenance=BUDGET_PROVENANCE,
        ),
        BudgetFact(
            entity_siren=owner_siren,
            exercice=2025,
            mission="MIRES",
            programme="172",
            amount_ae_eur=8_259_807_441,
            amount_cp_eur=8_701_105_312,
            executed=False,
            provenance=BUDGET_PROVENANCE,
        ),
    ]


def _seed_contracts() -> list[Contract]:
    """Two real DECP marchés where the CNRS (acheteur SIREN 180089013) is the buyer.

    Source: « Données essentielles de la commande publique consolidées (format tabulaire) »,
    DAJ/Etalab, data.gouv.fr resource 22847056-61df-452d-837d-8b8ceadbfc52 (extrait 2026-06-09).
    Licence Ouverte 2.0. The acheteur is a seeded entity (CNRS); titulaires are external suppliers
    carried as SIRENs only (the UI renders an un-named titulaire by its SIREN). These contracts also
    drive the seed's ``delegates`` edges (FSC-39) via the shared ``core.contracts`` helper.
    """
    cnrs = "180089013"
    return [
        Contract(
            acheteur_siren=cnrs,
            titulaire_siren="329200521",
            montant_eur=1_800_000,
            nature=Nature.marche,
            exercice=2026,
            provenance=DECP_PROVENANCE,
        ),
        Contract(
            acheteur_siren=cnrs,
            titulaire_siren="326556578",
            montant_eur=84_925.39,
            nature=Nature.marche,
            exercice=2026,
            provenance=DECP_PROVENANCE,
        ),
    ]


@dataclass(frozen=True)
class SeedBundle:
    """The curated seed slice. Mirrors ``transforms.TransformResult`` but adds ``contracts``."""

    entities: list[Entity] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    budget_facts: list[BudgetFact] = field(default_factory=list)
    contracts: list[Contract] = field(default_factory=list)


def build_seed(
    *, crosswalk: Crosswalk | None = None, ministries: MinistryIndex | None = None
) -> SeedBundle:
    """Build the seed: ministry + operator entities, tutelle edges, budget facts, contracts.

    Loads the committed crosswalk + ministry reference by default; both are injectable for
    offline tests. Fails loud if a selected operator is missing/unresolved in the crosswalk or its
    tutelle does not resolve to a ministry — the seed must never carry a guessed SIREN.
    """
    crosswalk = crosswalk if crosswalk is not None else load_crosswalk()
    ministries = ministries if ministries is not None else MinistryIndex.load()

    ministries_by_siren: dict[str, Entity] = {}
    operators: list[Entity] = []
    edges: list[Edge] = []

    for denomination, category in _SEED_OPERATORS:
        key = normalize_name(denomination)
        entry = crosswalk.get(key)
        operator_siren = crosswalk.resolve(key)
        if entry is None or operator_siren is None:
            raise ValueError(
                f"seed operator {denomination!r} is not an accepted (auto/reviewed) crosswalk row"
            )
        ministry = ministries.resolve(entry.tutelle)
        if ministry is None or ministry.siren is None:
            raise ValueError(
                f"seed operator {denomination!r} has no resolvable tutelle ministry "
                f"(tutelle={entry.tutelle!r})"
            )
        ministries_by_siren.setdefault(
            ministry.siren,
            Entity(
                siren=ministry.siren,
                name=ministry.denomination,
                level=Level.state,
                category=MINISTRY_CATEGORY,
                provenance=PROVENANCE,
            ),
        )
        operators.append(
            Entity(
                siren=operator_siren,
                name=denomination,
                level=Level.state,
                category=category,
                parent_siren=ministry.siren,
                provenance=PROVENANCE,
            )
        )
        edges.append(
            Edge(
                source_siren=ministry.siren,
                target_siren=operator_siren,
                type=EdgeType.tutelle,
                provenance=PROVENANCE,
            )
        )

    # Resolve the MIRES budget owner (MESR) from the ministry reference — never a hardcoded SIREN.
    # It is also a seeded entity (its operator CNRS pins it above), so the budget fact hangs off the
    # graph; the referential-integrity test guards that invariant.
    budget_owner = ministries.resolve(_BUDGET_MISSION_OWNER_TUTELLE)
    if budget_owner is None or budget_owner.siren is None:
        raise ValueError(
            f"seed budget owner ministry {_BUDGET_MISSION_OWNER_TUTELLE!r} "
            "does not resolve to a SIREN"
        )

    # Real DECP contracts → aggregated `delegates` edges (CNRS → titulaire), the same derivation the
    # production DECP transform uses (single source of truth, golden rule). Titulaires are kept as
    # bare-SIREN targets (no entity row, no fabricated name) — the UI renders them as such, and the
    # contracts/edges are queryable via `graph_neighbors` (FSC-39). The two edge layers carry
    # distinct provenances so a provenance-scoped reload replaces exactly its own rows.
    contracts = _seed_contracts()
    delegates_edges = aggregate_delegates_edges(contracts)
    all_edges = edges + delegates_edges

    # Deterministic order: ministries (graph roots) first, then operators — both by SIREN.
    ministry_entities = sorted(ministries_by_siren.values(), key=lambda e: e.siren or "")
    operator_entities = sorted(operators, key=lambda e: e.siren or "")
    return SeedBundle(
        entities=ministry_entities + operator_entities,
        edges=sorted(all_edges, key=lambda e: (e.type.value, e.source_siren, e.target_siren)),
        budget_facts=_seed_budget_facts(budget_owner.siren),
        contracts=contracts,
    )


# --------------------------------------------------------------------------- #
# SQL rendering — deterministic, so the committed seed.sql is a stable golden file.
# --------------------------------------------------------------------------- #
_SQL_HEADER = """\
-- supabase/seed.sql — committed curated seed (FSC-24). GENERATED, do not edit by hand:
-- regenerate with `make seed` (source: packages/ingestion/src/ingestion/seed.py).
--
-- A tiny, real, licence-attributed État-central slice so a fresh dev DB and Vercel previews render
-- a populated graph + entity sheet without the full ingestion load (FSC-35). DEV/PREVIEW ONLY —
-- never apply to the curated production database (it truncates the curated tables first).
--
-- Provenance & licence (all Licence Ouverte / Etalab 2.0):
--   * Ministries, operators, tutelle edges — resolved from data/crosswalk/*.yaml (Jaune
--     « Opérateurs de l'État », Direction du budget; ministry SIRENs verified via
--     recherche-entreprises, nature juridique 7113).
--   * Budget facts — PLF 2025, mission MIRES, voté (programmes 150 & 172), attributed to the
--     owning ministry MESR (the budget holder; SIREN resolved from the ministry reference).
--     Source: Sénat, rapport général PLF 2025 — Recherche et enseignement supérieur
--     (https://www.senat.fr/rap/l24-144-324/l24-144-324_mono.html) + budget.gouv.fr PAP.
--   * Contracts — DECP consolidées (DAJ/Etalab), data.gouv.fr resource
--     22847056-61df-452d-837d-8b8ceadbfc52 (extrait 2026-06-09).
"""


def render_sql(bundle: SeedBundle) -> str:
    """Serialize a :class:`SeedBundle` to a deterministic, idempotent seed SQL script."""
    sections = [
        _SQL_HEADER,
        "\nbegin;",
        "\n-- Idempotent: clear the curated tables, then re-insert the seed slice.",
        "truncate entities, edges, budget_facts, contracts, attributions, mentions "
        "restart identity cascade;",
        "\n-- Entities: ministries (graph roots) then operators.",
        render_insert("entities", ENTITY_COLUMNS, list(bundle.entities)),
        "-- Edges: tutelle (ministry -> operator) + delegates (acheteur -> titulaire, from DECP).",
        render_insert("edges", EDGE_COLUMNS, list(bundle.edges)),
        "-- Budget facts: PLF 2025 MIRES, voté (mission/programme grain).",
        render_insert("budget_facts", BUDGET_COLUMNS, list(bundle.budget_facts)),
        "-- Contracts: real DECP marchés (CNRS acheteur).",
        render_insert("contracts", CONTRACT_COLUMNS, list(bundle.contracts)),
        "\ncommit;\n",
    ]
    return "\n".join(sections)


def emit_seed_sql(path: Path | str = SEED_SQL_PATH) -> Path:
    """Render the seed and write it to ``path`` (the committed ``supabase/seed.sql``)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sql(build_seed()), encoding="utf-8")
    return path
