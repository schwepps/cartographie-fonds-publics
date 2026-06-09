"""Tests for the ILLUSTRATIVE demo seed (FSC-50…53).

Unlike the real seed (``test_seed.py``), this dataset is intentionally illustrative, so the tests
pin its *shape* and honesty conventions rather than provenance against the crosswalk:

* all four administrative levels are present, with funds / participation / delegates flows;
* the two anonymous DECP titulaires are edge endpoints with **no entity row** (the « SIREN non
  résolu » case the UI must handle);
* referential integrity for the resolvable parts (edge sources, tutelle edges, budgets, contracts);
* no drift — the committed ``supabase/demo_seed.sql`` is byte-for-byte what the builder renders.
"""

from __future__ import annotations

from core.models import BudgetFact, Contract, Edge, EdgeType, Entity, Level
from ingestion.demo_seed import (
    DEMO_SQL_PATH,
    build_demo,
    emit_demo_sql,
    render_sql,
)

_UNRESOLVED_TITULAIRES = {"329200521", "326556578"}


def test_build_demo_validates_against_frozen_model() -> None:
    bundle = build_demo()
    assert bundle.entities and bundle.edges and bundle.budget_facts and bundle.contracts
    assert all(isinstance(e, Entity) for e in bundle.entities)
    assert all(isinstance(e, Edge) for e in bundle.edges)
    assert all(isinstance(b, BudgetFact) for b in bundle.budget_facts)
    assert all(isinstance(c, Contract) for c in bundle.contracts)


def test_covers_all_four_levels_and_all_edge_types() -> None:
    bundle = build_demo()
    assert {e.level for e in bundle.entities} == set(Level)
    assert {e.type for e in bundle.edges} == set(EdgeType)


def test_unresolved_titulaires_have_no_entity_row() -> None:
    """The « SIREN non résolu » case: titulaires referenced by edges/contracts but not seeded."""
    bundle = build_demo()
    siren_set = {e.siren for e in bundle.entities}
    edge_targets = {e.target_siren for e in bundle.edges}
    assert edge_targets >= _UNRESOLVED_TITULAIRES
    assert not (_UNRESOLVED_TITULAIRES & siren_set)


def test_referential_integrity_of_resolvable_parts() -> None:
    bundle = build_demo()
    siren_set = {e.siren for e in bundle.entities}

    # Every edge source is a seeded entity (only delegates *targets* may be unresolved titulaires).
    assert all(e.source_siren in siren_set for e in bundle.edges)
    # tutelle edges connect two seeded entities; operators point up to a seeded parent.
    for edge in bundle.edges:
        if edge.type is EdgeType.tutelle:
            assert edge.target_siren in siren_set
    for entity in bundle.entities:
        if entity.parent_siren is not None:
            assert entity.parent_siren in siren_set
    # Budget facts hang off a seeded entity; contracts off a seeded acheteur.
    assert all(b.entity_siren in siren_set for b in bundle.budget_facts)
    assert all(c.acheteur_siren in siren_set for c in bundle.contracts)


def test_has_a_multi_year_budget_for_the_trend_spark() -> None:
    """At least one entity carries budget rows across ≥2 exercices (voted + executed)."""
    bundle = build_demo()
    by_entity: dict[str | None, set[int]] = {}
    for fact in bundle.budget_facts:
        by_entity.setdefault(fact.entity_siren, set()).add(fact.exercice)
    assert any(len(years) >= 2 for years in by_entity.values())
    assert {f.executed for f in bundle.budget_facts} == {True, False}


def test_committed_demo_seed_sql_is_in_sync_with_builder() -> None:
    """Golden/drift guard: committed demo_seed.sql == a fresh render (run `make demo-seed`)."""
    assert DEMO_SQL_PATH.exists(), "supabase/demo_seed.sql is missing — run `make demo-seed`"
    expected = render_sql(build_demo())
    actual = DEMO_SQL_PATH.read_text(encoding="utf-8")
    assert actual == expected, "supabase/demo_seed.sql is stale — regenerate with `make demo-seed`"


def test_render_is_deterministic_and_idempotent(tmp_path) -> None:
    bundle = build_demo()
    assert render_sql(bundle) == render_sql(bundle)
    sql = render_sql(bundle)
    assert (
        "truncate entities, edges, budget_facts, contracts, attributions, mentions "
        "restart identity cascade;" in sql
    )
    assert sql.strip().startswith("--") and sql.rstrip().endswith("commit;")
    out = emit_demo_sql(tmp_path / "demo_seed.sql")
    assert out.read_text(encoding="utf-8") == sql
