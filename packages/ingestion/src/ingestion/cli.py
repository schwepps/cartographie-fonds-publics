"""Ingestion CLI (stub). `python -m ingestion.cli ingest|refresh`."""

from __future__ import annotations

import typer

from .connectors import Connector, UnknownPlatformError, get_connector
from .registry import Source, sources

app = typer.Typer(help="Registry-driven ingestion pipeline.")


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


if __name__ == "__main__":
    app()
