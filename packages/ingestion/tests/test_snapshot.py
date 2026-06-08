"""Snapshot harness tests — atomic Parquet write, provenance round-trip, keep-last-valid (AC3)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from ingestion import snapshot
from ingestion.errors import SnapshotError
from ingestion.snapshot import read_provenance, write_snapshot

_AT = "2026-06-08T12:00:00Z"


def test_snapshot_writes_parquet_with_roundtrip_provenance(tmp_path: Path) -> None:
    raw = b"acheteur_siren,montant\n180089013,1250000\n130005481,840000\n"
    path = write_snapshot(
        raw,
        source_id="decp",
        extracted_at=_AT,
        source_ref="https://example.test/decp.csv",
        license="Licence Ouverte 2.0",
        schema_ref="decp_schema.json",
        cell_warnings=3,
        root=tmp_path,
    )

    assert path.exists()
    assert path.parent == tmp_path / "decp"  # written under root/<source_id>/

    prov = read_provenance(path)
    assert prov.source_id == "decp"
    assert prov.content_sha256 == hashlib.sha256(raw).hexdigest()  # hash of RAW bytes
    assert prov.byte_size == len(raw)
    assert prov.row_count == 2
    assert prov.license == "Licence Ouverte 2.0"
    assert prov.schema_ref == "decp_schema.json"
    assert prov.cell_warnings == 3
    assert prov.extracted_at == _AT

    pointer = json.loads((tmp_path / "decp" / "latest.json").read_text())
    assert pointer["snapshot"] == path.name
    assert not list((tmp_path / "decp").glob("*.tmp"))  # no orphaned temp files


def test_failed_write_keeps_last_valid_snapshot(tmp_path: Path, monkeypatch) -> None:
    src_dir = tmp_path / "decp"
    v1 = write_snapshot(b"a,b\n1,x\n", source_id="decp", extracted_at=_AT, root=tmp_path)
    v1_bytes = v1.read_bytes()
    pointer_before = (src_dir / "latest.json").read_text()

    # Simulate a crash during the atomic promotion of the NEW parquet (only .parquet targets).
    real_replace = snapshot.os.replace

    def flaky_replace(src, dst, *args, **kwargs):
        if str(dst).endswith(".parquet"):
            raise OSError("simulated mid-write failure")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(snapshot.os, "replace", flaky_replace)

    with pytest.raises(SnapshotError):
        write_snapshot(
            b"a,b\n9,z\n", source_id="decp", extracted_at="2026-06-08T13:00:00Z", root=tmp_path
        )

    # The previous valid snapshot and its pointer are untouched; no temp file leaks.
    assert v1.read_bytes() == v1_bytes
    assert (src_dir / "latest.json").read_text() == pointer_before
    assert not list(src_dir.glob("*.tmp"))


def test_parquet_is_queryable_and_preserves_text(tmp_path: Path) -> None:
    import duckdb

    raw = b"siren,montant\n010089013,1000\n"  # leading zero must survive (all_varchar)
    path = write_snapshot(raw, source_id="decp", extracted_at=_AT, root=tmp_path)
    rows = duckdb.connect().execute(f"SELECT siren FROM read_parquet('{path}')").fetchall()
    assert rows == [("010089013",)]


def test_unsupported_format_raises(tmp_path: Path) -> None:
    with pytest.raises(SnapshotError):
        write_snapshot(b"{}", source_id="decp", extracted_at=_AT, fmt="json", root=tmp_path)
