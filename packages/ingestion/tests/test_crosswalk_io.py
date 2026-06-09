"""Crosswalk I/O: round-trip, fail-loud loading, merge-preservation, and the CLI rate gate."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from core.crosswalk import CrosswalkEntry, CrosswalkStatus
from ingestion.cli import app
from ingestion.crosswalk_io import dump_entries, load_crosswalk, load_entries, merge_seed
from pydantic import ValidationError
from typer.testing import CliRunner

runner = CliRunner()


def _write_yaml(path: Path, rows: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"schema_version": 1, "entries": rows}), encoding="utf-8")


def test_round_trip_dump_then_load(tmp_path: Path) -> None:
    entries = [
        CrosswalkEntry(
            denomination="Centre national X", status=CrosswalkStatus.auto, siren="180089013"
        ),
        CrosswalkEntry(
            denomination="Backlog Op",
            status=CrosswalkStatus.pending,
            candidate_sirens=["111222333"],
        ),
    ]
    path = tmp_path / "operateurs.yaml"
    dump_entries(entries, path)
    cw = load_crosswalk(path)
    assert len(cw) == 2
    assert cw.resolve("centre national x") == "180089013"


def test_load_fails_loud_on_conflicting_collision(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    _write_yaml(
        path,
        [
            {"denomination": "École Normale", "status": "reviewed", "siren": "180089013"},
            {"denomination": "ecole normale", "status": "reviewed", "siren": "775685019"},
        ],
    )
    with pytest.raises(ValueError, match="conflicting SIRENs"):
        load_crosswalk(path)


def test_load_fails_loud_on_malformed_siren(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    _write_yaml(path, [{"denomination": "Bad", "status": "reviewed", "siren": "abc"}])
    with pytest.raises(ValidationError):  # bubbles up from CrosswalkEntry construction
        load_entries(path)


def test_merge_preserves_reviewed_and_category_rows() -> None:
    existing = [
        CrosswalkEntry(
            denomination="Curated Op",
            status=CrosswalkStatus.reviewed,
            siren="775685019",
            reviewed_by="alice",
        ),
        CrosswalkEntry(denomination="Universités et assimilés", status=CrosswalkStatus.category),
    ]
    seed = [
        # The seed would overwrite "Curated Op" as auto with a different SIREN — must NOT win.
        CrosswalkEntry(denomination="Curated Op", status=CrosswalkStatus.auto, siren="180089013"),
        CrosswalkEntry(denomination="New Op", status=CrosswalkStatus.auto, siren="130005481"),
    ]
    merged = {e.normalized_name: e for e in merge_seed(seed, existing)}
    assert merged["curated op"].status is CrosswalkStatus.reviewed
    assert merged["curated op"].siren == "775685019"  # curation preserved
    assert merged["curated op"].reviewed_by == "alice"
    assert merged["universites assimiles"].status is CrosswalkStatus.category
    assert merged["new op"].siren == "130005481"  # fresh seed row added


def _gate_setup(tmp_path: Path, *, siren_for_op: bool) -> tuple[Path, Path, Path]:
    crosswalk = tmp_path / "cw.yaml"
    status, siren = ("auto", "180089013") if siren_for_op else ("pending", None)
    row = {"denomination": "Op One", "status": status}
    if siren:
        row["siren"] = siren
    _write_yaml(crosswalk, [row])
    operators = tmp_path / "ops.csv"
    operators.write_text("operateur\nOp One\n", encoding="utf-8")
    return crosswalk, operators, tmp_path / "report.json"


def test_cli_resolve_passes_above_threshold(tmp_path: Path) -> None:
    crosswalk, operators, out = _gate_setup(tmp_path, siren_for_op=True)
    result = runner.invoke(
        app,
        [
            "resolve",
            "--operators",
            str(operators),
            "--crosswalk",
            str(crosswalk),
            "--out",
            str(out),
            "--min-rate",
            "0.5",
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_cli_resolve_exits_nonzero_below_threshold(tmp_path: Path) -> None:
    crosswalk, operators, out = _gate_setup(tmp_path, siren_for_op=False)
    result = runner.invoke(
        app,
        [
            "resolve",
            "--operators",
            str(operators),
            "--crosswalk",
            str(crosswalk),
            "--out",
            str(out),
            "--min-rate",
            "0.5",
        ],
    )
    assert result.exit_code == 1, result.output
    assert out.exists()  # report still written before the gate fails


def test_cli_resolve_unknown_name_column_fails(tmp_path: Path) -> None:
    crosswalk, operators, out = _gate_setup(tmp_path, siren_for_op=True)
    result = runner.invoke(
        app,
        [
            "resolve",
            "--operators",
            str(operators),
            "--crosswalk",
            str(crosswalk),
            "--out",
            str(out),
            "--name-column",
            "missing",
        ],
    )
    assert result.exit_code != 0
