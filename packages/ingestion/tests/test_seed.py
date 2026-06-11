"""Tests for the committed curated seed (FSC-24).

The seed builder constructs frozen-model instances, so "validates against the frozen model" is
enforced by construction; these tests pin the rest of the contract:

* **referential integrity** — tutelle edge endpoints / operator parents resolve to a seeded entity,
  and contracts + delegates edges attach to a seeded acheteur so they hang off the graph (their
  titulaires are external suppliers, carried by SIREN only);
* **real SIRENs** — operator/ministry SIRENs come from the committed crosswalk YAMLs, never
  hardcoded in the builder (golden rule #1/#5);
* **no drift** — the committed ``supabase/seed.sql`` is byte-for-byte what the builder renders, so
  a stale artifact fails loud (mirrors the crosswalk regeneration discipline).
"""

from __future__ import annotations

import pytest
from core.crosswalk import Crosswalk
from core.models import BudgetFact, Contract, Edge, EdgeType, Entity, Level
from core.resolve import normalize_name
from ingestion.crosswalk_io import load_crosswalk, load_ministries
from ingestion.seed import (
    MINISTRY_CATEGORY,
    SEED_SQL_PATH,
    build_seed,
    emit_seed_sql,
    render_sql,
)
from ingestion.transforms.operateurs_etat import MinistryIndex


def test_build_seed_validates_against_frozen_model() -> None:
    bundle = build_seed()
    # Construction already ran Pydantic validation (SIREN format, enums, extra="forbid"); assert the
    # slice is non-empty and every slot holds the right frozen type.
    assert bundle.entities and bundle.edges and bundle.budget_facts and bundle.contracts
    assert all(isinstance(e, Entity) for e in bundle.entities)
    assert all(isinstance(e, Edge) for e in bundle.edges)
    assert all(isinstance(b, BudgetFact) for b in bundle.budget_facts)
    assert all(isinstance(c, Contract) for c in bundle.contracts)
    # Everything in the seed is État-central.
    assert all(e.level is Level.state for e in bundle.entities)


def test_entities_split_into_ministries_and_operators() -> None:
    bundle = build_seed()
    ministries = [e for e in bundle.entities if e.category == MINISTRY_CATEGORY]
    operators = [e for e in bundle.entities if e.category != MINISTRY_CATEGORY]
    # A few of each, ministries before operators (graph roots first).
    assert len(ministries) >= 2
    assert len(operators) >= 3
    assert bundle.entities[: len(ministries)] == ministries
    # Ministries are roots; operators point up to their tutelle ministry.
    assert all(m.parent_siren is None for m in ministries)
    assert all(o.parent_siren is not None for o in operators)


def test_referential_integrity() -> None:
    bundle = build_seed()
    siren_set = {e.siren for e in bundle.entities}

    # Every operator's tutelle ministry is itself a seeded entity.
    for operator in bundle.entities:
        if operator.parent_siren is not None:
            assert operator.parent_siren in siren_set

    # Edge sources are always seeded entities (a ministry for tutelle, the acheteur for delegates).
    # Tutelle edges connect two seeded entities; delegates edges point to an external supplier
    # (titulaire) carried by SIREN only — it need not be a seeded entity (the UI renders it bare).
    for edge in bundle.edges:
        assert edge.source_siren in siren_set
        if edge.type is EdgeType.tutelle:
            assert edge.target_siren in siren_set

    # Budget facts attach to the mission's owning ministry (MESR, the budget holder) — itself a
    # seeded entity — never to a receiving operator (golden rule #8, anti-double-counting).
    ministries_by_siren = {e.siren: e for e in bundle.entities if e.category == MINISTRY_CATEGORY}
    for fact in bundle.budget_facts:
        assert fact.entity_siren in ministries_by_siren

    # Contracts hang off the graph via a seeded acheteur (titulaires are external suppliers).
    assert all(c.acheteur_siren in siren_set for c in bundle.contracts)


def test_seed_rows_carry_a_registry_resolvable_provenance() -> None:
    """Entities and edges are stamped with a real registry source id (not a 'seed' sentinel), so the
    web provenance UI can resolve them to a source name. The État-central skeleton is the Jaune
    « Opérateurs de l'État »; the delegates edges/contracts are DECP."""
    bundle = build_seed()
    assert all(e.provenance == "operateurs_etat" for e in bundle.entities)
    # tutelle from the operators source, delegates from DECP — both real registry ids.
    assert all(
        edge.provenance in {"operateurs_etat", "decp_commande_publique"} for edge in bundle.edges
    )
    assert any(edge.provenance == "decp_commande_publique" for edge in bundle.edges)  # delegates
    assert all(c.provenance == "decp_commande_publique" for c in bundle.contracts)


def test_sirens_come_from_the_committed_crosswalk() -> None:
    """No SIREN is hardcoded in the builder: operators resolve via the crosswalk, ministries via the
    reviewed ministry reference."""
    bundle = build_seed()
    crosswalk = load_crosswalk()
    ministry_sirens = {e.siren for e in load_ministries()}
    ministries = MinistryIndex.load()

    for entity in bundle.entities:
        if entity.category == MINISTRY_CATEGORY:
            assert entity.siren in ministry_sirens
        else:
            # The operator's SIREN is exactly what the crosswalk resolves its name to.
            assert entity.siren == crosswalk.resolve(normalize_name(entity.name))
            # And its parent is the ministry its crosswalk tutelle points at.
            entry = crosswalk.get(normalize_name(entity.name))
            assert entry is not None
            ministry = ministries.resolve(entry.tutelle)
            assert ministry is not None
            assert entity.parent_siren == ministry.siren


def test_build_seed_fails_loud_on_unresolved_operator() -> None:
    """golden rule #5: a seeded operator absent from the crosswalk must raise, never guess."""
    empty_crosswalk = Crosswalk.from_entries([])
    with pytest.raises(ValueError, match="not an accepted"):
        build_seed(crosswalk=empty_crosswalk, ministries=MinistryIndex.load())


def test_build_seed_fails_loud_on_unresolved_tutelle() -> None:
    """An operator resolves but its tutelle maps to no ministry → raise, never anchor blind."""
    no_ministries = MinistryIndex([])  # resolves nothing
    with pytest.raises(ValueError, match="no resolvable tutelle ministry"):
        build_seed(crosswalk=load_crosswalk(), ministries=no_ministries)


def test_committed_seed_sql_is_in_sync_with_builder() -> None:
    """Golden/drift guard: the committed seed.sql must equal a fresh render (run `make seed`)."""
    assert SEED_SQL_PATH.exists(), "supabase/seed.sql is missing — run `make seed`"
    expected = render_sql(build_seed())
    actual = SEED_SQL_PATH.read_text(encoding="utf-8")
    assert actual == expected, "supabase/seed.sql is stale — regenerate with `make seed`"


def test_render_is_deterministic_and_idempotent(tmp_path) -> None:
    bundle = build_seed()
    # Same input -> identical bytes (byte-stable golden file).
    assert render_sql(bundle) == render_sql(bundle)
    # The SQL truncates before inserting, so re-applying is idempotent.
    sql = render_sql(bundle)
    assert (
        "truncate entities, edges, budget_facts, contracts, attributions, mentions "
        "restart identity cascade;" in sql
    )
    assert sql.strip().startswith("--") and sql.rstrip().endswith("commit;")
    # emit writes exactly what render produces.
    out = emit_seed_sql(tmp_path / "seed.sql")
    assert out.read_text(encoding="utf-8") == sql
