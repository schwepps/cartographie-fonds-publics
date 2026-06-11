"""Snapshot harness tests — atomic Parquet write, provenance round-trip, keep-last-valid (AC3)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from ingestion import snapshot
from ingestion.errors import SnapshotError, UnsupportedFormatError
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


def test_pointer_write_failure_keeps_last_valid_and_no_orphan(tmp_path: Path, monkeypatch) -> None:
    src_dir = tmp_path / "decp"
    v1 = write_snapshot(b"a,b\n1,x\n", source_id="decp", extracted_at=_AT, root=tmp_path)
    pointer_before = (src_dir / "latest.json").read_text()
    parquets_before = sorted(p.name for p in src_dir.glob("*.parquet"))

    def boom(*args, **kwargs):
        raise OSError("pointer write failed")

    monkeypatch.setattr(snapshot, "_write_pointer", boom)

    with pytest.raises(SnapshotError):
        write_snapshot(
            b"a,b\n9,z\n", source_id="decp", extracted_at="2026-06-08T13:00:00Z", root=tmp_path
        )

    # Pointer unchanged AND the promoted parquet was rolled back -> no orphan, no temp leak.
    assert (src_dir / "latest.json").read_text() == pointer_before
    assert sorted(p.name for p in src_dir.glob("*.parquet")) == parquets_before
    assert not list(src_dir.glob("*.tmp"))
    assert v1.exists()


@pytest.mark.parametrize("bad", ["../evil", "a/b", "a\\b", "", ".", "..", "/abs"])
def test_unsafe_source_id_rejected(tmp_path: Path, bad: str) -> None:
    with pytest.raises(SnapshotError):
        write_snapshot(b"a,b\n1,x\n", source_id=bad, extracted_at=_AT, root=tmp_path)


def test_unsupported_format_raises(tmp_path: Path) -> None:
    # csv + json are supported (FSC-47); anything else is still a capability limit.
    with pytest.raises(UnsupportedFormatError):
        write_snapshot(b"\x00", source_id="decp", extracted_at=_AT, fmt="parquet", root=tmp_path)


def test_snapshot_json_writes_parquet_with_format_provenance(tmp_path: Path) -> None:
    import duckdb

    # siren as a leading-zero string + montant as a JSON int: both must round-trip as faithful text.
    raw = b'[{"siren": "010089013", "montant": 1000}, {"siren": "217500016", "montant": 2000}]'
    path = write_snapshot(raw, source_id="ofgl", extracted_at=_AT, fmt="json", root=tmp_path)

    prov = read_provenance(path)
    assert prov.format == "json"
    assert prov.content_sha256 == hashlib.sha256(raw).hexdigest()  # hash of the RAW json bytes
    assert prov.byte_size == len(raw)
    assert prov.row_count == 2

    rows = (
        duckdb.connect()
        .execute(f"SELECT siren, montant FROM read_parquet('{path}') ORDER BY siren")
        .fetchall()
    )
    assert rows == [("010089013", "1000"), ("217500016", "2000")]  # all_varchar text preserved


def test_snapshot_json_unwraps_envelope(tmp_path: Path) -> None:
    import duckdb

    raw = b'{"total_count": 2, "results": [{"siren": "200054781"}, {"siren": "217500016"}]}'
    path = write_snapshot(
        raw, source_id="ofgl", extracted_at=_AT, fmt="json", record_path="results", root=tmp_path
    )
    assert read_provenance(path).row_count == 2
    count = duckdb.connect().execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()
    assert count is not None and count[0] == 2


def test_snapshot_empty_json_array_yields_zero_rows(tmp_path: Path) -> None:
    # An empty array snapshots cleanly at 0 rows (the validate step is where emptiness fails loud).
    path = write_snapshot(b"[]", source_id="ofgl", extracted_at=_AT, fmt="json", root=tmp_path)
    prov = read_provenance(path)
    assert prov.format == "json"
    assert prov.row_count == 0


def test_malformed_json_snapshot_fails_loud(tmp_path: Path) -> None:
    # A bad envelope (results is an object, not an array) fails loud rather than snapshotting empty.
    with pytest.raises(SnapshotError):
        write_snapshot(
            b'{"results": {}}',
            source_id="ofgl",
            extracted_at=_AT,
            fmt="json",
            record_path="results",
            root=tmp_path,
        )
