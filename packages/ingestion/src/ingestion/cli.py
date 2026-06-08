"""Ingestion CLI (stub). `python -m ingestion.cli ingest|refresh`."""

from __future__ import annotations

import typer

from .registry import sources

app = typer.Typer(help="Registry-driven ingestion pipeline.")


@app.command()
def ingest() -> None:
    """Run discover -> extract -> validate -> snapshot -> stage for all sources."""
    for s in sources():
        typer.echo(f"[ingest] {s.id} ({s.layer}) — TODO connector")


@app.command()
def refresh() -> None:
    """Discover the latest millesime for each source (no frozen slugs)."""
    for s in sources():
        typer.echo(f"[refresh] {s.id}: {s.discovery.get('strategy', 'n/a')}")


if __name__ == "__main__":
    app()
