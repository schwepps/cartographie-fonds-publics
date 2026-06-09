"""Load the curated État-central graph into Supabase (FSC-35).

The connectors snapshot raw extracts and the transforms (``ingestion.transforms``) curate them into
:class:`~ingestion.transforms.TransformResult` slices (entities + tutelle edges from the operators
source; budget facts from the State-budget sources). This module is the **load stage**: it reads
the latest snapshot for each curated État-central source, runs its transform, merges the slices, and
renders an **idempotent, provenance-scoped** SQL script that the ``load`` Makefile target applies
via ``psql`` (direct ``DATABASE_URL`` — the service-role path; ``service_role`` bypasses RLS, so the
public-read policies are untouched). Same mechanism as ``seed`` / ``db-migrate`` — no DB driver.

**Idempotency — why provenance-scoped, not a whole-table truncate.** ``entities``/``edges``/
``budget_facts`` get *multiple* writers over the roadmap (delegates edges from DECP, participation
edges from SEM/SPL, local + social budget facts), and the loader runs on a schedule against prod.
So each table is rebuilt **per provenance scope**, never wholesale:

* ``entities`` — ``INSERT … ON CONFLICT (siren) DO UPDATE`` (accretive across sources, keyed on the
  canonical SIREN). Unresolved entities (``siren=None``) are dropped and **counted** in the summary
  (golden rule #5: never silently drop), since there is no key to upsert on.
* ``edges`` / ``budget_facts`` — ``DELETE WHERE provenance IN (this load's sources)`` then
  ``INSERT``. This makes the load *authoritative for its own provenance scope*: orphaned rows (a
  relationship that vanished upstream) are removed, while another source's rows are never touched.

Re-running is a no-op on row counts (delete-then-insert of a deterministically-ordered bundle). The
whole script runs in one ``begin … commit`` under ``ON_ERROR_STOP`` — atomic, fail-loud.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.models import BudgetFact, Edge, Entity

from .errors import LoadError
from .snapshot import SNAPSHOT_ROOT, read_snapshot_rows
from .sql_render import BUDGET_COLUMNS, EDGE_COLUMNS, ENTITY_COLUMNS, render_insert, sql_literal
from .transforms import TransformResult, get_transform
from .transforms.operateurs_etat import MINISTRY_CATEGORY

# The curated État-central source set (Phase 1): the three registered transforms that write the
# curated graph. Each source_id doubles as the `provenance` stamped on the rows it produces.
ETAT_CENTRAL_SOURCE_IDS: tuple[str, ...] = (
    "operateurs_etat",
    "budget_plf_lfi",
    "budget_execution_mensuelle",
)

# Emit path for the rendered load SQL (gitignored `out/`, like the other CLI reports). Env-override
# mirrors crosswalk_io / seed (CFP_* prefix), so an installed env can point it elsewhere.
_DEFAULT_LOAD_SQL_PATH = Path(__file__).resolve().parents[4] / "out" / "load.sql"
LOAD_SQL_PATH = Path(os.environ.get("CFP_LOAD_SQL_PATH", _DEFAULT_LOAD_SQL_PATH))

# Entities are accretive (keyed by the canonical SIREN): a reload updates the row rather than
# deleting it, so an entity another source still references is never dropped.
_ENTITY_ON_CONFLICT = (
    "on conflict (siren) do update set "
    "name = excluded.name, level = excluded.level, category = excluded.category, "
    "parent_siren = excluded.parent_siren, provenance = excluded.provenance"
)

# (headers, rows) reader for a source_id — injectable so the merge is unit-testable without a
# snapshot tree on disk.
ReadRows = Callable[[str], tuple[list[str], list[dict[str, str]]]]


@dataclass(frozen=True)
class LoadBundle:
    """The curated slice to load + the metadata the SQL render and the summary need."""

    entities: list[Entity]  # deduped by SIREN; siren is never None (unresolved are dropped)
    edges: list[Edge]  # deduped by (source, target, type, exercice)
    budget_facts: list[BudgetFact]  # as emitted (entity_siren may be None — a LOLF-level fact)
    provenances: tuple[str, ...]  # provenance scopes this load rebuilds (the source_ids)
    skipped_unresolved: int  # entities dropped for siren=None (reported, never silent)
    reports: dict[str, dict[str, Any]]  # per source_id transform report (for the summary)


def build_bundle(
    source_ids: tuple[str, ...] = ETAT_CENTRAL_SOURCE_IDS,
    *,
    snapshot_root: Path = SNAPSHOT_ROOT,
    read_rows: ReadRows | None = None,
    allow_empty: bool = False,
) -> LoadBundle:
    """Read each source's latest snapshot, transform it, and merge into one curated bundle.

    Pure of any DB. ``read_rows`` defaults to reading the latest snapshot under ``snapshot_root``;
    inject it for offline tests. Fails loud (``LoadError``) if a source contributes zero rows — its
    snapshot is empty/broken and a provenance-scoped reload would delete its existing rows with
    nothing to re-insert — unless ``allow_empty``.
    """
    read = read_rows or (lambda source_id: read_snapshot_rows(source_id, root=snapshot_root))

    entities_by_siren: dict[str, Entity] = {}
    edges_by_key: dict[tuple[str, str, str, int | None], Edge] = {}
    budget_facts: list[BudgetFact] = []
    reports: dict[str, dict[str, Any]] = {}
    skipped_unresolved = 0

    for source_id in source_ids:
        headers, rows = read(source_id)
        result: TransformResult = get_transform(source_id)(headers, rows)
        reports[source_id] = result.report
        if not (result.entities or result.edges or result.budget_facts) and not allow_empty:
            raise LoadError(
                f"source {source_id!r} produced 0 curated rows from its snapshot — refusing to "
                "load (a provenance-scoped reload would delete its existing rows with no "
                "replacement). Check the snapshot, or pass allow_empty=True to override."
            )
        for entity in result.entities:
            if entity.siren is None:  # unresolved — no key to upsert on; counted, never silent
                skipped_unresolved += 1
                continue
            entities_by_siren.setdefault(entity.siren, entity)
        for edge in result.edges:
            edges_by_key.setdefault(
                (edge.source_siren, edge.target_siren, edge.type.value, edge.exercice), edge
            )
        budget_facts.extend(result.budget_facts)

    return LoadBundle(
        entities=sorted(entities_by_siren.values(), key=lambda e: e.siren or ""),
        edges=sorted(
            edges_by_key.values(), key=lambda e: (e.source_siren, e.target_siren, e.type.value)
        ),
        budget_facts=sorted(
            budget_facts,
            key=lambda f: (
                f.provenance or "",
                f.exercice,
                f.mission or "",
                f.programme or "",
                f.executed,
            ),
        ),
        provenances=tuple(source_ids),
        skipped_unresolved=skipped_unresolved,
        reports=reports,
    )


_SQL_HEADER = """\
-- out/load.sql — curated État-central load (FSC-35). GENERATED, do not edit by hand:
-- regenerate with `make load` (source: packages/ingestion/src/ingestion/load.py).
--
-- Idempotent + provenance-scoped: entities upsert on SIREN; edges and budget_facts are rebuilt per
-- source (delete-by-provenance then insert), so a reload replaces exactly the sources in this load
-- — orphaned rows are removed and other sources' rows (e.g. delegates edges) are left untouched.
-- Applied in one transaction via `psql -v ON_ERROR_STOP=1` (service-role / direct DATABASE_URL).
"""


def render_load_sql(bundle: LoadBundle) -> str:
    """Serialize a :class:`LoadBundle` to an idempotent, provenance-scoped load script."""
    scope = ", ".join(sql_literal(provenance) for provenance in bundle.provenances)
    sections = [
        _SQL_HEADER,
        "\nbegin;",
        "\n-- Entities: upsert on the canonical SIREN (accretive across sources).",
        render_insert("entities", ENTITY_COLUMNS, bundle.entities, on_conflict=_ENTITY_ON_CONFLICT),
        "-- Edges: provenance-scoped rebuild (replace this load's sources; orphans removed, other",
        "-- sources' edges untouched).",
        f"delete from edges where provenance in ({scope});",
        render_insert("edges", EDGE_COLUMNS, bundle.edges),
        "-- Budget facts: provenance-scoped rebuild (same contract as edges).",
        f"delete from budget_facts where provenance in ({scope});",
        render_insert("budget_facts", BUDGET_COLUMNS, bundle.budget_facts),
        "\ncommit;\n",
    ]
    return "\n".join(sections)


def load_summary(bundle: LoadBundle) -> str:
    """A human-readable load summary — counts, not row dumps (golden rule #6; feeds FSC-43)."""
    ministries = [e for e in bundle.entities if e.category == MINISTRY_CATEGORY]
    edges_by_type: dict[str, int] = {}
    for edge in bundle.edges:
        edges_by_type[edge.type.value] = edges_by_type.get(edge.type.value, 0) + 1
    voted = sum(1 for f in bundle.budget_facts if not f.executed)
    executed = sum(1 for f in bundle.budget_facts if f.executed)
    op_report = bundle.reports.get("operateurs_etat", {})
    rate = op_report.get("resolution_rate")

    lines = [
        f"[load] sources: {', '.join(bundle.provenances)}",
        f"  entities: {len(bundle.entities)} "
        f"({len(ministries)} ministries, {len(bundle.entities) - len(ministries)} operators)"
        + (
            f"; {bundle.skipped_unresolved} unresolved skipped" if bundle.skipped_unresolved else ""
        ),
        f"  edges: {len(bundle.edges)} ("
        + ", ".join(f"{count} {etype}" for etype, count in sorted(edges_by_type.items()))
        + ")"
        if bundle.edges
        else "  edges: 0",
        f"  budget_facts: {len(bundle.budget_facts)} ({voted} voted, {executed} executed)",
    ]
    if rate is not None:
        lines.append(f"  operator SIREN resolution rate: {float(rate):.0%}")
    return "\n".join(lines)


def emit_load_sql(
    path: Path | str = LOAD_SQL_PATH,
    *,
    source_ids: tuple[str, ...] = ETAT_CENTRAL_SOURCE_IDS,
    snapshot_root: Path = SNAPSHOT_ROOT,
    allow_empty: bool = False,
) -> tuple[Path, LoadBundle]:
    """Build the bundle from the latest snapshots and write the load SQL to ``path``."""
    bundle = build_bundle(source_ids, snapshot_root=snapshot_root, allow_empty=allow_empty)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_load_sql(bundle), encoding="utf-8")
    return path, bundle
