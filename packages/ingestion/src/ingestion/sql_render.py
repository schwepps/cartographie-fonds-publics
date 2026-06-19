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
ATTRIBUTION_COLUMNS = ("entity_siren", "legal_ref", "txt", "source_url", "provenance")
MENTION_COLUMNS = (
    "entity_siren",
    "report_ref",
    "report_date",
    "mention_type",
    "url",
    "note",
    "provenance",
    "license",
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


# Rows per INSERT statement. A single multi-row INSERT of the full curated graph (e.g. ~1.2M edges /
# ~2M DECP contracts) is one giant statement that exhausts the Postgres backend's memory and drops
# the connection — so large tables are emitted as a sequence of bounded INSERTs (all inside the
# loader's single transaction, so the load stays atomic). The threshold is far above any seed/demo
# table, so their single-batch output (and the seed's pinned golden SQL) stays byte-for-byte equal.
_BATCH_SIZE = 5000


def render_insert(
    table: str,
    columns: tuple[str, ...],
    rows: Sequence[BaseModel],
    *,
    on_conflict: str | None = None,
    batch_size: int = _BATCH_SIZE,
) -> str:
    """Render multi-row INSERT(s) for ``rows`` (pydantic models), or a comment if empty.

    Rows are split into statements of at most ``batch_size`` so a very large table cannot crash the
    Postgres backend on one oversized statement. With ``len(rows) <= batch_size`` exactly one INSERT
    is emitted, byte-for-byte as before (the seed/demo golden tests depend on this). ``on_conflict``
    appends an ``ON CONFLICT …`` clause to **each** statement (the upsert applies per batch).
    """
    if not rows:
        return f"-- (no {table} rows)\n"
    cols = ", ".join(columns)
    suffix = f"\n{on_conflict}" if on_conflict else ""

    def value_line(r: BaseModel) -> str:
        dumped = r.model_dump(mode="json")
        return "  (" + ", ".join(sql_literal(dumped[c]) for c in columns) + ")"

    statements = [
        f"insert into {table} ({cols}) values\n"
        + ",\n".join(value_line(r) for r in rows[start : start + batch_size])
        + suffix
        + ";\n"
        for start in range(0, len(rows), batch_size)
    ]
    return "".join(statements)
