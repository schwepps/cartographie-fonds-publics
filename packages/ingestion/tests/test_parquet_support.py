"""Tests for the FSC-38 parquet ingestion path (DECP is published as a ~10x-smaller parquet).

Covers: parquet snapshot round-trip (all_varchar faithfulness — SIREN leading zeros survive),
structural parquet validation (missing column = drift, extra column = tolerated), and the
connector's preferred-format resource selection.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
from ingestion.connectors.datagouv_api import DatagouvApiConnector
from ingestion.errors import SchemaValidationError
from ingestion.snapshot import read_provenance, read_snapshot_rows, write_snapshot
from ingestion.validation import validate_extract


def _parquet_bytes(tmp_path: Path, rows_sql: str, columns: str) -> bytes:
    """Build a small parquet file via duckdb and return its bytes."""
    src = tmp_path / "src.parquet"
    con = duckdb.connect()
    try:
        con.execute(f"CREATE TABLE s AS SELECT * FROM (VALUES {rows_sql}) t({columns})")
        con.execute(f"COPY s TO '{src}' (FORMAT PARQUET)")
    finally:
        con.close()
    return src.read_bytes()


def test_write_snapshot_parquet_roundtrip_preserves_leading_zeros(tmp_path) -> None:  # type: ignore[no-untyped-def]
    raw = _parquet_bytes(
        tmp_path, "('012345678','Acme',100),('987654321','Beta',200)", "siren,nom,montant"
    )
    root = tmp_path / "snaps"
    path = write_snapshot(
        raw,
        source_id="decp_commande_publique",
        extracted_at="2026-06-19T00:00:00+00:00",
        fmt="parquet",
        root=root,
    )
    prov = read_provenance(path)
    assert prov.format == "parquet"
    assert prov.row_count == 2
    headers, rows = read_snapshot_rows("decp_commande_publique", root=root)
    assert headers == ["siren", "nom", "montant"]
    assert rows[0]["siren"] == "012345678"  # all_varchar: leading zero survived
    assert rows[0]["montant"] == "100"  # native int rendered as text


def _schema_file(tmp_path: Path, names: list[str]) -> str:
    path = tmp_path / "schema.json"
    path.write_text(
        json.dumps({"fields": [{"name": n, "type": "string"} for n in names]}), encoding="utf-8"
    )
    return str(path)


def test_validate_parquet_columns_ok(tmp_path) -> None:  # type: ignore[no-untyped-def]
    raw = _parquet_bytes(tmp_path, "('a','b')", "acheteur_id,titulaire_id")
    schema_ref = _schema_file(tmp_path, ["acheteur_id", "titulaire_id"])
    report = validate_extract(raw, source_id="decp", schema_ref=schema_ref, fmt="parquet")
    assert report.skipped is False


def test_validate_parquet_missing_column_is_drift(tmp_path) -> None:  # type: ignore[no-untyped-def]
    raw = _parquet_bytes(tmp_path, "('a')", "acheteur_id")
    schema_ref = _schema_file(tmp_path, ["acheteur_id", "titulaire_id"])  # titulaire_id absent
    with pytest.raises(SchemaValidationError):
        validate_extract(raw, source_id="decp", schema_ref=schema_ref, fmt="parquet")


def test_validate_parquet_extra_column_is_tolerated(tmp_path) -> None:  # type: ignore[no-untyped-def]
    raw = _parquet_bytes(tmp_path, "('a','b','c')", "acheteur_id,titulaire_id,newcol")
    schema_ref = _schema_file(tmp_path, ["acheteur_id", "titulaire_id"])  # newcol not in schema
    report = validate_extract(raw, source_id="decp", schema_ref=schema_ref, fmt="parquet")
    assert (
        report.skipped is False
    )  # the transform reads by name; a new upstream column must not fail


def test_select_resource_prefers_declared_format() -> None:
    dataset = {
        "title": "DECP",
        "resources": [
            {"format": "csv", "filesize": 2_000_000_000, "url": "csv", "id": "1"},
            {"format": "parquet", "filesize": 200_000_000, "url": "parquet", "id": "2"},
        ],
    }
    chosen = DatagouvApiConnector._select_resource(dataset, preferred_format="parquet")
    assert chosen["url"] == "parquet"  # parquet wins despite the CSV being 10x larger
    # No preference → the largest CSV (existing behaviour) still wins.
    assert DatagouvApiConnector._select_resource(dataset)["url"] == "csv"
