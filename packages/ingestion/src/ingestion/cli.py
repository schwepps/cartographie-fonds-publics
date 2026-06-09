"""Ingestion CLI (stub). `python -m ingestion.cli ingest|refresh|resolve|resolve-seed`."""

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
    dump_entries,
    load_crosswalk,
    load_entries,
    merge_seed,
)
from .crosswalk_io import _row_to_seed_entry as row_to_seed_entry
from .registry import Source, sources

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

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    typer.echo(
        f"[resolve] {report['resolved']}/{report['total']} resolved "
        f"(rate {result.resolution_rate:.0%}); {report['unresolved']} unresolved -> {out}"
    )
    for reason, count in sorted(report["unresolved_by_reason"].items()):
        if count:
            typer.echo(f"  {reason}: {count}")
    if result.resolution_rate < min_rate:
        typer.echo(
            f"[resolve] resolution rate {result.resolution_rate:.0%} < {min_rate:.0%} threshold",
            err=True,
        )
        raise typer.Exit(code=1)


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
    with open(resolution_csv, encoding="utf-8") as fh:
        seed = [row_to_seed_entry(row) for row in csv.DictReader(fh)]
    existing = load_entries(crosswalk) if Path(crosswalk).exists() else []
    merged = merge_seed(seed, existing)
    dump_entries(merged, crosswalk, maintainer=maintainer)
    preserved = sum(
        1
        for e in existing
        if e.normalized_name in {m.normalized_name for m in merged}
        and e.status.value in {"reviewed", "category"}
    )
    typer.echo(
        f"[resolve-seed] wrote {len(merged)} entries to {crosswalk} (preserved {preserved} curated)"
    )


if __name__ == "__main__":
    app()
