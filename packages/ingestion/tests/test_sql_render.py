"""Tests for INSERT batching in sql_render (FSC-38).

A single multi-row INSERT of the full curated graph (~1.2M edges / ~2M contracts) crashes the
Postgres backend, so large tables are split into bounded statements. Small inputs (seed/demo) must
still emit exactly one statement so their pinned golden SQL stays byte-for-byte unchanged.
"""

from __future__ import annotations

from core.models import Entity, Level
from ingestion.sql_render import ENTITY_COLUMNS, render_insert


def _entities(n: int) -> list[Entity]:
    return [Entity(name=f"E{i}", siren=f"{i:09d}", level=Level.state) for i in range(n)]


def test_empty_rows_render_a_comment() -> None:
    assert render_insert("entities", ENTITY_COLUMNS, []) == "-- (no entities rows)\n"


def test_small_input_is_a_single_statement() -> None:
    sql = render_insert("entities", ENTITY_COLUMNS, _entities(3))
    assert sql.count("insert into entities") == 1  # ≤ batch: one statement (byte-identical legacy)
    assert sql.endswith(";\n")


def test_large_input_is_chunked_into_bounded_statements() -> None:
    sql = render_insert("entities", ENTITY_COLUMNS, _entities(12), batch_size=5)
    assert sql.count("insert into entities") == 3  # 5 + 5 + 2
    for i in range(12):  # every row is still emitted exactly once — nothing dropped
        assert sql.count(f"'{i:09d}'") == 1


def test_on_conflict_applies_to_every_batch() -> None:
    sql = render_insert(
        "entities",
        ENTITY_COLUMNS,
        _entities(12),
        on_conflict="on conflict (siren) do nothing",
        batch_size=5,
    )
    assert sql.count("on conflict (siren) do nothing") == 3  # the upsert holds per chunk
