"""Deterministic SQL rendering for the curated tables — shared by the seed and the loader.

Both the committed dev/preview seed (``ingestion.seed``, FSC-24) and the production curated
loader (``ingestion.load``, FSC-35) serialize the same frozen domain models (``core.models``) to
SQL ``insert`` statements. The literal rendering and the column tuples live here so the two stay
byte-for-byte consistent (the seed's golden test pins exactly this output) and there is one place
that knows how a Python value becomes a SQL literal.

Rendering is *deterministic*: same models in, same SQL out (integral floats stay integers; rows are
emitted in the order given). Callers are responsible for ordering their rows for stable output.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum

from pydantic import BaseModel

# Business columns per curated table (the DB-generated uuid ``id`` is intentionally excluded — it is
# not a domain concern; see ``core.models``). Order is the rendered column order; keep it stable.
ENTITY_COLUMNS = ("siren", "name", "level", "category", "parent_siren", "provenance")
EDGE_COLUMNS = ("source_siren", "target_siren", "type", "amount_eur", "exercice", "provenance")
BUDGET_COLUMNS = (
    "entity_siren",
    "exercice",
    "mission",
    "programme",
    "amount_ae_eur",
    "amount_cp_eur",
    "executed",
    "nomenclature",
    "provenance",
)
CONTRACT_COLUMNS = (
    "acheteur_siren",
    "titulaire_siren",
    "montant_eur",
    "nature",
    "exercice",
    "provenance",
)


def sql_literal(value: object) -> str:
    """Render a Python value as a SQL literal (deterministic; integral floats stay integers)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, float):
        # Fail loud rather than emit `nan`/`inf` — invalid in a numeric INSERT (cf.
        # crosswalk_io._parse_ratio, which rejects non-finite floats the same way).
        if not math.isfinite(value):
            raise ValueError(f"non-finite amount cannot be rendered to SQL: {value!r}")
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def render_insert(
    table: str,
    columns: tuple[str, ...],
    rows: Sequence[BaseModel],
    *,
    on_conflict: str | None = None,
) -> str:
    """Render a single multi-row INSERT for ``rows`` (pydantic models), or a comment if empty.

    ``on_conflict`` appends an ``ON CONFLICT …`` clause (e.g. an upsert) before the terminating
    semicolon; omitted (the seed's case) it renders a plain INSERT byte-for-byte as before.
    """
    if not rows:
        return f"-- (no {table} rows)\n"
    values = [
        "  (" + ", ".join(sql_literal(r.model_dump(mode="json")[c]) for c in columns) + ")"
        for r in rows
    ]
    cols = ", ".join(columns)
    suffix = f"\n{on_conflict}" if on_conflict else ""
    return f"insert into {table} ({cols}) values\n" + ",\n".join(values) + suffix + ";\n"
