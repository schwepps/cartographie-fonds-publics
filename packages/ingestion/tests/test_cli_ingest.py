"""Offline CLI tests for the FSC-38 ingest orchestrator and the `load --scope` selector.

The orchestrator is driven with fake connectors (no network): we assert the per-source
discover→extract→validate→snapshot ordering, all-or-nothing routing (no side effect before a
routing failure), the ok/skipped/failed classification, and that `--discover-only` stops after
discovery. The load tests assert the right curated source set + reader are passed through.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ingestion import cli
from ingestion.cli import app
from ingestion.connectors import UnknownPlatformError
from ingestion.errors import SnapshotError
from ingestion.load import ALL_SOURCE_IDS, EDITORIAL_SOURCE_IDS
from ingestion.registry import Source
from typer.testing import CliRunner

runner = CliRunner()


def _src(source_id: str, *, platform: str = "datagouv_api") -> Source:
    return Source(id=source_id, raw={"id": source_id, "platform": platform, "layer": "test"})


def _text(result: Any) -> str:
    """Combined stdout+stderr, robust across Click versions (mixed vs separately captured)."""
    text = result.output or ""
    try:
        if result.stderr:
            text += result.stderr
    except ValueError:  # old Click: stderr already folded into output
        pass
    return text


class _FakeConnector:
    """Records the pipeline steps it is asked to run; configurable to fail at a chosen stage."""

    def __init__(
        self,
        recorder: list[tuple[str, str]],
        *,
        source_id: str,
        has_credentials: bool = True,
        discover_exc: Exception | None = None,
        snapshot_exc: Exception | None = None,
    ) -> None:
        self._rec = recorder
        self._sid = source_id
        self.has_credentials = has_credentials
        self._discover_exc = discover_exc
        self._snapshot_exc = snapshot_exc

    def discover(self, source: dict[str, Any]) -> dict[str, Any]:
        self._rec.append((self._sid, "discover"))
        if self._discover_exc is not None:
            raise self._discover_exc
        return {"title": f"{self._sid} dataset"}

    def extract(self, resolved: dict[str, Any]) -> bytes:
        self._rec.append((self._sid, "extract"))
        return b"col\n1\n"

    def validate(self, raw: bytes, schema_ref: str | None) -> None:
        self._rec.append((self._sid, "validate"))

    def snapshot(self, raw: bytes, source_id: str) -> str:
        self._rec.append((self._sid, "snapshot"))
        if self._snapshot_exc is not None:
            raise self._snapshot_exc
        return f"/snap/{source_id}.parquet"

    def stage(self, snapshot_uri: str, source_id: str) -> None:  # pragma: no cover - unused
        raise NotImplementedError


# --------------------------------------------------------------------------- ingest


def test_ingest_only_runs_full_pipeline_in_order(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rec: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "sources", lambda: [_src("operateurs_etat")])
    monkeypatch.setattr(cli, "get_connector", lambda s: _FakeConnector(rec, source_id=s.id))
    result = runner.invoke(app, ["ingest", "--only", "operateurs_etat"])
    assert result.exit_code == 0
    assert rec == [
        ("operateurs_etat", "discover"),
        ("operateurs_etat", "extract"),
        ("operateurs_etat", "validate"),
        ("operateurs_etat", "snapshot"),
    ]
    assert "1 ok" in _text(result)


def test_ingest_aborts_before_any_extract_when_a_source_is_unroutable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rec: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "sources", lambda: [_src("a"), _src("b")])

    def fake_get_connector(s: Source) -> _FakeConnector:
        if s.id == "b":
            raise UnknownPlatformError("no connector for b")
        return _FakeConnector(rec, source_id=s.id)

    monkeypatch.setattr(cli, "get_connector", fake_get_connector)
    result = runner.invoke(app, ["ingest", "--only", "a", "--only", "b"])
    assert result.exit_code == 1
    assert rec == []  # all-or-nothing: nothing ran before the routing failure
    assert "UNROUTABLE b" in _text(result)


def test_ingest_reports_failure_and_exits_nonzero(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rec: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "sources", lambda: [_src("a")])
    monkeypatch.setattr(
        cli,
        "get_connector",
        lambda s: _FakeConnector(rec, source_id=s.id, discover_exc=ValueError("no dataset")),
    )
    result = runner.invoke(app, ["ingest", "--only", "a"])
    assert result.exit_code == 1
    assert "FAIL a" in _text(result)
    assert "1 failed" in _text(result)


def test_ingest_discover_only_stops_after_discovery(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rec: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "sources", lambda: [_src("a")])
    monkeypatch.setattr(cli, "get_connector", lambda s: _FakeConnector(rec, source_id=s.id))
    result = runner.invoke(app, ["ingest", "--only", "a", "--discover-only"])
    assert result.exit_code == 0
    assert rec == [("a", "discover")]  # no extract / validate / snapshot


def test_ingest_skips_source_without_credentials(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rec: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "sources", lambda: [_src("legifrance_attributions", platform="rest")])
    monkeypatch.setattr(
        cli,
        "get_connector",
        lambda s: _FakeConnector(rec, source_id=s.id, has_credentials=False),
    )
    result = runner.invoke(app, ["ingest", "--only", "legifrance_attributions"])
    assert result.exit_code == 0
    assert rec == []  # never attempted without the secret
    assert "1 skipped" in _text(result)


def test_ingest_skips_editorial_non_tabular_snapshot(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rec: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "sources", lambda: [_src("cour_des_comptes")])
    monkeypatch.setattr(
        cli,
        "get_connector",
        lambda s: _FakeConnector(rec, source_id=s.id, snapshot_exc=SnapshotError("pdf")),
    )
    result = runner.invoke(app, ["ingest", "--only", "cour_des_comptes"])
    assert result.exit_code == 0  # editorial source loads from YAML; snapshot is provenance-only
    assert "1 skipped" in _text(result)


def test_ingest_non_editorial_snapshot_error_is_a_failure(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rec: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "sources", lambda: [_src("operateurs_etat")])
    monkeypatch.setattr(
        cli,
        "get_connector",
        lambda s: _FakeConnector(rec, source_id=s.id, snapshot_exc=SnapshotError("disk full")),
    )
    result = runner.invoke(app, ["ingest", "--only", "operateurs_etat"])
    assert result.exit_code == 1
    assert "1 failed" in _text(result)


def test_ingest_unknown_only_id_fails_loud(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(cli, "sources", lambda: [_src("a")])
    result = runner.invoke(app, ["ingest", "--only", "nope"])
    assert result.exit_code != 0
    assert "unknown source id" in _text(result)


def test_ingest_default_targets_are_the_load_sources(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rec: list[tuple[str, str]] = []
    ids = list(ALL_SOURCE_IDS) + ["cour_des_comptes"]  # editorial present in the registry
    monkeypatch.setattr(cli, "sources", lambda: [_src(i) for i in ids])
    seen: list[str] = []

    def gc(s: Source) -> _FakeConnector:
        seen.append(s.id)
        return _FakeConnector(rec, source_id=s.id)

    monkeypatch.setattr(cli, "get_connector", gc)
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 0
    assert set(seen) == set(ALL_SOURCE_IDS)  # editorial excluded from the default set


# --------------------------------------------------------------------------- load --scope


def _patch_emit(monkeypatch, captured: dict[str, Any]) -> None:
    def fake_emit(
        out: Path,
        *,
        source_ids: tuple[str, ...],
        snapshot_root: Path,
        read_rows: Any,
        allow_empty: bool,
    ) -> tuple[Path, object]:
        captured["source_ids"] = source_ids
        captured["read_rows"] = read_rows
        return Path(out), object()

    monkeypatch.setattr(cli, "emit_load_sql", fake_emit)
    monkeypatch.setattr(cli, "load_summary", lambda bundle: "summary")


def test_load_scope_all_passes_all_source_ids(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, Any] = {}
    _patch_emit(monkeypatch, captured)
    result = runner.invoke(app, ["load", "--scope", "all", "--out", str(tmp_path / "l.sql")])
    assert result.exit_code == 0
    assert captured["source_ids"] == ALL_SOURCE_IDS
    assert captured["read_rows"] is None


def test_load_scope_editorial_uses_empty_reader(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, Any] = {}
    _patch_emit(monkeypatch, captured)
    result = runner.invoke(app, ["load", "--scope", "editorial", "--out", str(tmp_path / "l.sql")])
    assert result.exit_code == 0
    assert captured["source_ids"] == EDITORIAL_SOURCE_IDS
    assert captured["read_rows"] is cli._empty_rows
    assert cli._empty_rows("anything") == ([], [])  # editorial transforms ignore snapshot rows


def test_load_unknown_scope_fails_loud(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["load", "--scope", "bogus", "--out", str(tmp_path / "l.sql")])
    assert result.exit_code != 0
    assert "unknown scope" in _text(result)


def test_load_only_overrides_scope_with_explicit_sources(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, Any] = {}
    _patch_emit(monkeypatch, captured)
    # --only loads exactly the listed snapshot-backed sources, ignoring --scope (the escape hatch
    # when a --scope all source has no live data yet).
    result = runner.invoke(
        app,
        [
            "load",
            "--only",
            "operateurs_etat",
            "--only",
            "decp_commande_publique",
            "--out",
            str(tmp_path / "l.sql"),
        ],
    )
    assert result.exit_code == 0
    assert captured["source_ids"] == ("operateurs_etat", "decp_commande_publique")
    assert captured["read_rows"] is None
