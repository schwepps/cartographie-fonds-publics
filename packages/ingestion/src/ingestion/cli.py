"""Ingestion CLI (stub). Commands: ingest, refresh, resolve, operators, budget, resolve-seed,
seed-emit."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Annotated

import typer
from core.models import Entity, Level
from core.resolution import resolve_entities

from .connectors import Connector, UnknownPlatformError, get_connector
from .crosswalk_io import (
    CROSSWALK_PATH,
    CURATED_STATUSES,
    dump_entries,
    load_crosswalk,
    load_entries,
    load_seed_csv,
    merge_seed,
)
from .registry import Source, sources
from .seed import SEED_SQL_PATH, emit_seed_sql
from .tabular import parse_csv_bytes
from .transforms import get_transform

app = typer.Typer(help="Registry-driven ingestion pipeline.")

# Resolution rate below this fails the run (CI gate). Matches the Phase-0.5 spike's RESOLVE_MIN.
RESOLVE_RATE_MIN = 0.5


def _resolve(s: Source) -> Connector | None:
    """Route a source to its connector, or report a clear SKIP and return None.

    Warn-and-continue is deliberate: golden-rule "fail loud" targets data drift, not the
    stub phase where most platforms have no connector yet. We still exit nonzero (see the
    callers) so CI stays red until every source is routed.
    """
    try:
        return get_connector(s)
    except UnknownPlatformError as exc:
        typer.echo(f"  SKIP {s.id}: {exc}", err=True)
        return None


@app.command()
def ingest() -> None:
    """Run discover -> extract -> validate -> snapshot -> stage for all sources."""
    routed = missing = 0
    for s in sources():
        connector = _resolve(s)
        if connector is None:
            missing += 1
            continue
        routed += 1
        typer.echo(f"[ingest] {s.id} ({s.layer}) — {type(connector).__name__}")
        # TODO: connector.discover -> extract -> validate -> snapshot -> stage.
        # Once stage() writes to Supabase, revisit warn-and-continue: a partial run would
        # persist some sources while skipping others. Consider an all-or-nothing routing
        # pre-check before any side effects.
    if missing:
        typer.echo(f"[ingest] routed {routed}, skipped {missing}", err=True)
        raise typer.Exit(code=1)


@app.command()
def refresh() -> None:
    """Discover the latest millesime for each source (no frozen slugs)."""
    routed = missing = 0
    for s in sources():
        connector = _resolve(s)
        if connector is None:
            missing += 1
            continue
        routed += 1
        typer.echo(f"[refresh] {s.id}: {s.discovery.get('strategy', 'n/a')}")
    if missing:
        typer.echo(f"[refresh] routed {routed}, skipped {missing}", err=True)
        raise typer.Exit(code=1)


def _read_operator_names(path: Path, name_column: str) -> list[str]:
    """Read operator names from a CSV; fail loud if the name column is absent."""
    with open(path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or name_column not in reader.fieldnames:
            raise typer.BadParameter(
                f"{path}: no {name_column!r} column (headers: {reader.fieldnames})"
            )
        return [name for row in reader if (name := (row.get(name_column) or "").strip())]


def _write_report(report: dict[str, object], out: Path) -> None:
    """Write the resolution report as deterministic JSON (sorted keys, gitignored out dir)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _echo_summary(report: dict[str, object], resolution_rate: float, out: Path) -> None:
    """Print the headline counts + the per-reason breakdown of unresolved links."""
    typer.echo(
        f"[resolve] {report['resolved']}/{report['total']} resolved "
        f"(rate {resolution_rate:.0%}); {report['unresolved']} unresolved -> {out}"
    )
    by_reason: dict[str, int] = report["unresolved_by_reason"]  # type: ignore[assignment]
    for reason, count in sorted(by_reason.items()):
        if count:
            typer.echo(f"  {reason}: {count}")


@app.command()
def resolve(
    operators: Annotated[
        Path, typer.Option(help="CSV of entity names to resolve (offline sample).")
    ],
    name_column: Annotated[
        str, typer.Option(help="Name column in the operators CSV.")
    ] = "operateur",
    crosswalk: Annotated[Path, typer.Option(help="Crosswalk YAML path.")] = CROSSWALK_PATH,
    out: Annotated[Path, typer.Option(help="Report output path.")] = Path(
        "out/resolution_report.json"
    ),
    min_rate: Annotated[
        float, typer.Option(help="Exit nonzero below this resolution rate.")
    ] = RESOLVE_RATE_MIN,
) -> None:
    """Resolve entities on SIREN via the crosswalk; write the unresolved-links report + rate.

    Every input is accounted for (resolved or unresolved — never dropped). Exits nonzero when the
    resolution rate drops below the threshold, surfacing the metric to CI.
    """
    cw = load_crosswalk(crosswalk)
    entities = [
        Entity(name=name, siren=None, level=Level.state)
        for name in _read_operator_names(operators, name_column)
    ]
    result = resolve_entities(entities, cw)
    report = result.to_report_dict()
    _write_report(report, out)
    _echo_summary(report, result.resolution_rate, out)
    if result.resolution_rate < min_rate:
        typer.echo(
            f"[resolve] resolution rate {result.resolution_rate:.0%} < {min_rate:.0%} threshold",
            err=True,
        )
        raise typer.Exit(code=1)


@app.command()
def operators(
    csv_path: Annotated[
        Path, typer.Option("--operators", help="CSV of Jaune operators (offline sample).")
    ],
    out: Annotated[Path, typer.Option(help="Report output path.")] = Path(
        "out/operators_report.json"
    ),
    min_rate: Annotated[
        float, typer.Option(help="Exit nonzero below this resolution rate.")
    ] = RESOLVE_RATE_MIN,
) -> None:
    """Transform the Jaune operators into entities + tutelle edges; write the report + rate.

    Resolves operator SIRENs via the crosswalk and tutelle ministries via the curated reference,
    emitting `ministry -> operator` edges for resolved pairs. Every operator is accounted for —
    resolved (an entity with a SIREN) or unresolved (kept, surfaced in the report — never dropped,
    golden rule #5). Exits nonzero below the resolution-rate threshold, surfacing the metric to CI.
    """
    headers, rows = parse_csv_bytes(Path(csv_path).read_bytes())
    result = get_transform("operateurs_etat")(headers, rows)
    report = result.report
    _write_report(report, out)
    rate = float(report["resolution_rate"])
    typer.echo(
        f"[operators] {report['resolved']}/{report['total']} operators resolved (rate {rate:.0%}); "
        f"{len(result.entities)} entities ({report['ministries']} ministries), "
        f"{report['tutelle_edges']} tutelle edges -> {out}"
    )
    by_reason: dict[str, int] = report["unresolved_by_reason"]  # type: ignore[assignment]
    for reason, count in sorted(by_reason.items()):
        if count:
            typer.echo(f"  {reason}: {count}")
    if rate < min_rate:
        typer.echo(f"[operators] resolution rate {rate:.0%} < {min_rate:.0%} threshold", err=True)
        raise typer.Exit(code=1)


@app.command()
def budget(
    plf: Annotated[
        Path | None, typer.Option(help="PLF/LFI 'dépenses' CSV (offline sample).")
    ] = None,
    execution: Annotated[
        Path | None, typer.Option(help="Situation mensuelle CSV (offline sample).")
    ] = None,
    out: Annotated[Path, typer.Option(help="Report output path.")] = Path("out/budget_report.json"),
) -> None:
    """Transform State-budget CSVs into budget facts (voted + executed); write a counts report.

    Pure offline run: each provided CSV is curated via its registered transform into ``BudgetFact``
    rows — voted from PLF/LFI (`--plf`), executed from the monthly situation (`--execution`).
    Persistence to Supabase is FSC-35's job; this proves the facts are produced and validate.
    """
    inputs = {"budget_plf_lfi": plf, "budget_execution_mensuelle": execution}
    if not any(inputs.values()):
        raise typer.BadParameter("provide --plf and/or --execution")
    per_source: dict[str, object] = {}
    for source_id, path in inputs.items():
        if path is None:
            continue
        headers, rows = parse_csv_bytes(Path(path).read_bytes())
        result = get_transform(source_id)(headers, rows)
        per_source[source_id] = result.report
        typer.echo(
            f"[budget] {source_id}: {result.report['facts_out']} facts from "
            f"{result.report['rows_in']} rows (exercices {result.report['exercices']}) -> {out}"
        )
    _write_report({"sources": per_source}, out)


@app.command(name="resolve-seed")
def resolve_seed(
    resolution_csv: Annotated[
        Path, typer.Option(help="Spike operator_resolution.csv to seed from.")
    ],
    crosswalk: Annotated[
        Path, typer.Option(help="Crosswalk YAML to write (merge-aware).")
    ] = CROSSWALK_PATH,
    maintainer: Annotated[
        str, typer.Option(help="File maintainer.")
    ] = "contact@cartographie-fonds-publics.fr",
) -> None:
    """Regenerate the crosswalk from a resolver-spike CSV, preserving human-reviewed rows.

    Maintainer flow: `make spike-resolve[-live]` produces `operator_resolution.csv`; this folds it
    into the committed crosswalk — `unique` -> `auto`, `multiple`/`none` -> `pending` backlog —
    without clobbering any `reviewed`/`category` curation already in the file.
    """
    seed = load_seed_csv(resolution_csv)
    existing = load_entries(crosswalk) if Path(crosswalk).exists() else []
    merged = merge_seed(seed, existing)
    dump_entries(merged, crosswalk, maintainer=maintainer)
    preserved = sum(1 for e in existing if e.status in CURATED_STATUSES)
    typer.echo(
        f"[resolve-seed] wrote {len(merged)} entries to {crosswalk} (preserved {preserved} curated)"
    )


@app.command(name="seed-emit")
def seed_emit(
    out: Annotated[Path, typer.Option(help="Seed SQL file to write.")] = SEED_SQL_PATH,
) -> None:
    """Regenerate the committed curated seed (supabase/seed.sql) — FSC-24.

    A tiny, real, licence-attributed État-central slice (ministries + operators + tutelle edges +
    PLF 2025 MIRES budget facts + real DECP contracts) so a fresh dev DB / preview renders a
    populated graph without the full ingestion load. The artifact is generated — edit
    `ingestion.seed`, never the SQL. A golden test fails loud if the two drift.
    """
    written = emit_seed_sql(out)
    typer.echo(f"[seed-emit] wrote {written}")


if __name__ == "__main__":
    app()
