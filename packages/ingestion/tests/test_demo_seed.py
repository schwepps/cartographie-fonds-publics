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
    Nomenclature,
)
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


def test_has_an_aggregated_social_budget_slice() -> None:
    """The whole-perimeter overview (FSC-44) needs a real social headline: branche facts on a
    caisse, stamped ``social`` (aggregated module, attached to the caisse, not the graph)."""
    bundle = build_demo()
    social = [b for b in bundle.budget_facts if b.nomenclature is Nomenclature.social]
    assert social, "demo seed must carry at least one nomenclature=social budget fact (FSC-34/44)"
    assert all(b.entity_siren is not None and b.executed is True for b in social)


def test_has_illustrative_oversight_and_why_rows() -> None:
    """FSC-71: the demo must carry attributions (« why ») + mentions (« contrôle ») so the badge +
    both fiche sections render out-of-the-box on the default local/preview stack."""
    bundle = build_demo()
    assert bundle.attributions and bundle.mentions
    assert all(isinstance(a, Attribution) for a in bundle.attributions)
    assert all(isinstance(m, Mention) for m in bundle.mentions)


def test_oversight_why_rows_hang_off_seeded_entities() -> None:
    """Referential closure: every attribution/mention points at a seeded entity (no orphan rows)."""
    bundle = build_demo()
    siren_set = {e.siren for e in bundle.entities}
    assert all(a.entity_siren in siren_set for a in bundle.attributions)
    assert all(m.entity_siren in siren_set for m in bundle.mentions)


def test_mentions_trigger_the_badge_across_entities_and_both_types() -> None:
    """The « épinglé par la Cour » badge keys off the mentions table: it must light up several
    distinct nodes, and both mention types must be present so the fiche renders each."""
    bundle = build_demo()
    flagged = {m.entity_siren for m in bundle.mentions}
    assert len(flagged) >= 2
    assert {m.mention_type for m in bundle.mentions} == set(MentionType)


def test_oversight_why_rows_are_clearly_marked_example() -> None:
    """Honesty (golden rules #8/#10): the illustrative rows must be unmistakably « Exemple » so a
    preview visitor never reads them as a real Cour des comptes finding or legal mandate."""
    bundle = build_demo()
    for a in bundle.attributions:
        assert "Exemple" in (a.legal_ref or "") and "Exemple" in (a.txt or "")
    for m in bundle.mentions:
        assert "Exemple" in (m.report_ref or "") and "Exemple" in (m.note or "")


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
    # The illustrative oversight/why rows are emitted (FSC-71), not just truncated.
    assert "insert into attributions" in sql
    assert "insert into mentions" in sql
    assert sql.strip().startswith("--") and sql.rstrip().endswith("commit;")
    out = emit_demo_sql(tmp_path / "demo_seed.sql")
    assert out.read_text(encoding="utf-8") == sql
