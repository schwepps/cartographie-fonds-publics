"""Snapshot a validated raw extract to Parquet with embedded provenance (golden rule #4).

Heavy/raw extracts live as Parquet artifacts, never in git (see ARCHITECTURE.md / ``.gitignore``).
Each snapshot is written atomically and a per-source ``latest.json`` pointer only advances once
the new file is safely on disk — so a failed run **keeps the last valid snapshot in service**
(FSC-16 AC3). The ordering guarantee for AC3 lives at the call site: a connector validates()
*before* snapshot(); a drift raises and snapshot() is never reached.

Columns are stored as text (``all_varchar``): a raw snapshot must preserve the source bytes
faithfully (e.g. SIREN leading zeros), not impose a type. ``content_sha256`` over the raw bytes
is the reproducibility anchor; the Parquet file is the queryable artifact.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import duckdb
from pydantic import BaseModel, ConfigDict

from .errors import SnapshotError, UnsupportedFormatError

# Default root mirrors registry.REGISTRY_PATH resolution; env override for installed envs.
_DEFAULT_SNAPSHOT_ROOT = Path(__file__).resolve().parents[4] / "data" / "snapshots"
SNAPSHOT_ROOT = Path(os.environ.get("CFP_SNAPSHOT_ROOT", _DEFAULT_SNAPSHOT_ROOT))

_PROVENANCE_KEY = "cfp_provenance"
_LATEST_POINTER = "latest.json"
_UNSAFE_STAMP = re.compile(r"[^0-9A-Za-z]+")


class Provenance(BaseModel):
    """Self-describing snapshot metadata — travels inside the Parquet file's KV metadata.

    ``content_sha256`` is the hash of the *raw extract bytes* (computed before parsing), a stable
    reproducibility anchor even though the Parquet file itself embeds a timestamp.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    extracted_at: str  # ISO-8601 UTC; caller-supplied (keeps writes deterministic and testable)
    source_ref: str | None = None  # dataset / resource id or URL the extract came from
    license: str | None = None
    schema_ref: str | None = None
    content_sha256: str
    byte_size: int
    row_count: int
    format: str = "csv"
    cell_warnings: int = 0


def write_snapshot(
    raw: bytes,
    *,
    source_id: str,
    extracted_at: str,
    source_ref: str | None = None,
    license: str | None = None,
    schema_ref: str | None = None,
    cell_warnings: int = 0,
    fmt: str = "csv",
    root: Path = SNAPSHOT_ROOT,
) -> Path:
    """Persist ``raw`` as a provenance-tagged Parquet snapshot. Return the snapshot path.

    Atomic and non-destructive: the new file and the ``latest.json`` pointer are swapped in with
    ``os.replace`` only after a successful write, so any failure leaves the previous valid
    snapshot (and pointer) untouched. Raises ``SnapshotError`` on failure.
    """
    if fmt != "csv":
        raise UnsupportedFormatError(f"Cannot snapshot format {fmt!r} yet (only 'csv').")
    # source_id becomes a directory name — reject anything that isn't a single safe segment, so a
    # malformed registry id can never escape SNAPSHOT_ROOT or reach the COPY path interpolation.
    if (
        "/" in source_id
        or "\\" in source_id
        or os.path.isabs(source_id)
        or source_id in ("", ".", "..")
    ):
        raise SnapshotError(f"Unsafe source_id {source_id!r}: must be a single path segment.")

    target_dir = Path(root) / source_id
    target_dir.mkdir(parents=True, exist_ok=True)

    content_sha256 = hashlib.sha256(raw).hexdigest()
    byte_size = len(raw)

    raw_fd, raw_tmp = tempfile.mkstemp(dir=target_dir, suffix=".csv.tmp")
    parquet_tmp: str | None = None
    try:
        with os.fdopen(raw_fd, "wb") as fh:
            fh.write(raw)

        con = duckdb.connect()
        try:
            con.execute(
                "CREATE TABLE t AS SELECT * FROM read_csv(?, header=true, all_varchar=true)",
                [raw_tmp],
            )
            count_row = con.execute("SELECT count(*) FROM t").fetchone()
            row_count = int(count_row[0]) if count_row else 0

            provenance = Provenance(
                source_id=source_id,
                extracted_at=extracted_at,
                source_ref=source_ref,
                license=license,
                schema_ref=schema_ref,
                content_sha256=content_sha256,
                byte_size=byte_size,
                row_count=row_count,
                format=fmt,
                cell_warnings=cell_warnings,
            )

            fd2, parquet_tmp = tempfile.mkstemp(dir=target_dir, suffix=".parquet.tmp")
            os.close(fd2)
            # KV_METADATA key is a SQL identifier (interpolated); the value is bound as a param.
            con.execute(
                f"COPY t TO '{parquet_tmp}' (FORMAT PARQUET, KV_METADATA {{{_PROVENANCE_KEY}: ?}})",
                [provenance.model_dump_json()],
            )
        finally:
            con.close()

        final_path = target_dir / f"{_safe_stamp(extracted_at)}-{content_sha256[:8]}.parquet"
        os.replace(parquet_tmp, final_path)  # atomic within target_dir (same filesystem)
        parquet_tmp = None  # consumed — don't unlink in finally
        try:
            _write_pointer(target_dir / _LATEST_POINTER, final_path.name)
        except Exception:
            # Roll back the just-promoted file so a pointer failure leaves only the previous
            # valid snapshot (and its pointer) — never an orphaned, unreferenced parquet.
            _silent_unlink(final_path)
            raise
        return final_path
    except SnapshotError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface every write failure as a typed error
        raise SnapshotError(f"Failed to snapshot source {source_id!r}: {exc}") from exc
    finally:
        _silent_unlink(raw_tmp)
        if parquet_tmp is not None:
            _silent_unlink(parquet_tmp)


def read_provenance(path: Path | str) -> Provenance:
    """Read back the provenance embedded in a snapshot Parquet file."""
    con = duckdb.connect()
    try:
        rows = con.execute("SELECT key, value FROM parquet_kv_metadata(?)", [str(path)]).fetchall()
    finally:
        con.close()
    for key, value in rows:
        if _decode(key) == _PROVENANCE_KEY:
            return Provenance.model_validate_json(_decode(value))
    raise SnapshotError(f"No provenance metadata found in snapshot {path}")


def _write_pointer(pointer_path: Path, snapshot_filename: str) -> None:
    """Atomically point ``latest.json`` at the freshly written snapshot."""
    fd, tmp = tempfile.mkstemp(dir=pointer_path.parent, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"snapshot": snapshot_filename}, fh)
        os.replace(tmp, pointer_path)
    except BaseException:
        _silent_unlink(tmp)
        raise


def _safe_stamp(value: str) -> str:
    """Make an ISO timestamp safe for a filename (drop colons and other punctuation)."""
    return _UNSAFE_STAMP.sub("-", value).strip("-")


def _decode(value: bytes | str) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _silent_unlink(path: str | Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)
