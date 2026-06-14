"""Crosswalk I/O: round-trip, fail-loud loading, merge-preservation, and the CLI rate gate."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from core.crosswalk import CrosswalkEntry, CrosswalkStatus
from ingestion.cli import app
from ingestion.crosswalk_io import (
    dump_entries,
    load_crosswalk,
    load_entries,
    load_seed_csv,
    merge_seed,
    row_to_seed_entry,
)
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


def test_round_trip_preserves_zero_top_match_ratio(tmp_path: Path) -> None:
    # `0.0` is a meaningful value (a `none`-tier hint) and must survive the dump filter.
    entry = CrosswalkEntry(
        denomination="Unmatched Op", status=CrosswalkStatus.pending, top_match_ratio=0.0
    )
    path = tmp_path / "operateurs.yaml"
    dump_entries([entry], path)
    [loaded] = load_entries(path)
    assert loaded.top_match_ratio == 0.0


def test_round_trip_preserves_aliases(tmp_path: Path) -> None:
    # Curated matching aliases (FSC-70) must survive the dump→load round-trip.
    entry = CrosswalkEntry(
        denomination="France Travail",
        status=CrosswalkStatus.reviewed,
        siren="130005481",
        aliases=["Pôle emploi"],
    )
    path = tmp_path / "operateurs.yaml"
    dump_entries([entry], path)
    [loaded] = load_entries(path)
    assert loaded.aliases == ["Pôle emploi"]


def test_merge_carries_curated_aliases_onto_regenerated_row() -> None:
    # An operator hand-added an alias; a re-seed (which regenerates auto/pending rows) must not
    # silently drop it — even when the regenerated row carries no aliases of its own.
    existing = [
        CrosswalkEntry(
            denomination="France Travail",
            status=CrosswalkStatus.auto,
            siren="130005481",
            aliases=["Pôle emploi"],
        )
    ]
    seed = [
        CrosswalkEntry(
            denomination="France Travail", status=CrosswalkStatus.auto, siren="130005481"
        )
    ]
    [merged] = merge_seed(seed, existing)
    assert merged.aliases == ["Pôle emploi"]


def test_load_fails_loud_on_non_mapping_yaml(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("just a string\n", encoding="utf-8")
    with pytest.raises(ValueError, match="top-level YAML must be a mapping"):
        load_entries(path)


def test_load_fails_loud_on_unsupported_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump({"schema_version": 99, "entries": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported schema_version"):
        load_entries(path)


def test_load_fails_loud_on_missing_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump({"entries": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported schema_version"):
        load_entries(path)


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


_SEED_CSV = (
    "operateur,tutelle,normalized_name,tier,candidate_sirens,chosen_siren,top_match_ratio\n"
    "Unique Op,MEF,unique op,unique,180089013,180089013,1.0\n"
    "Ambiguous Op,MEF,ambiguous op,multiple,111222333|444555666,,1.0\n"
    "Unmatched Op,MEF,unmatched op,none,,,0.0\n"
)


def test_seed_csv_maps_tiers_to_statuses(tmp_path: Path) -> None:
    # Locks the CSV contract joining the throwaway spike to the production seed mapper (DRY seam).
    path = tmp_path / "operator_resolution.csv"
    path.write_text(_SEED_CSV, encoding="utf-8")
    by_name = {e.normalized_name: e for e in load_seed_csv(path)}
    assert by_name["unique op"].status is CrosswalkStatus.auto
    assert by_name["unique op"].siren == "180089013"
    assert by_name["ambiguous op"].status is CrosswalkStatus.pending
    assert by_name["ambiguous op"].candidate_sirens == ["111222333", "444555666"]
    assert by_name["unmatched op"].status is CrosswalkStatus.pending
    assert by_name["unmatched op"].top_match_ratio == 0.0  # zero hint preserved


def test_load_seed_csv_fails_loud_on_missing_column(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("operateur\nOnly a name\n", encoding="utf-8")  # no 'tier' column
    with pytest.raises(ValueError, match="missing required column"):
        load_seed_csv(path)


@pytest.mark.parametrize("bad", ["nan", "inf", "1.5", "-0.1", "abc"])
def test_row_to_seed_entry_rejects_invalid_ratio(bad: str) -> None:
    with pytest.raises(ValueError, match="top_match_ratio"):
        row_to_seed_entry({"operateur": "X", "tier": "none", "top_match_ratio": bad})


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
