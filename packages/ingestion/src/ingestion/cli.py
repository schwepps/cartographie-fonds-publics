"""Ingestion CLI. Commands: ingest, refresh, resolve, operators, budget, resolve-seed,
seed-emit, demo-seed-emit, load, attributions-candidates, extract-mentions, coverage,
curate-operators.

``ingest`` runs the registry-driven discover→extract→validate→snapshot loop (FSC-38) for the
curated load sources; ``load`` renders the provenance-scoped curated SQL from those snapshots
(FSC-35). Everything stays registry-driven — no dataset slug/URL is hardcoded here."""

from __future__ import annotations

import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
import yaml
from core.crosswalk import CrosswalkStatus
from core.models import Entity, Level
from core.resolution import resolve_entities

from .connectors import Connector, UnknownPlatformError, get_connector
from .connectors.rest import EXTRACT_ENVELOPE_KEY, RestConnector
from .crosswalk_io import (
    CROSSWALK_PATH,
    CURATED_STATUSES,
    dump_entries,
    load_crosswalk,
    load_entries,
    load_ministries,
    load_seed_csv,
    merge_seed,
)
from .curate_operators import SearchFn, curate
from .demo_seed import DEMO_SQL_PATH, emit_demo_sql
from .errors import SnapshotError, UnsupportedFormatError
from .load import (
    ALL_SOURCE_IDS,
    EDITORIAL_SOURCE_IDS,
    ETAT_CENTRAL_SOURCE_IDS,
    LOAD_SQL_PATH,
    emit_load_sql,
    load_summary,
)
from .mentions_candidates_io import CANDIDATES_PATH as MENTION_CANDIDATES_PATH
from .mentions_candidates_io import write_candidates as write_mention_candidates
from .registry import Source, get_source, sources
from .report_fetch import fetch_pdf
from .seed import SEED_SQL_PATH, emit_seed_sql
from .snapshot import SNAPSHOT_ROOT
from .tabular import parse_csv_bytes
from .transforms import get_transform
from .transforms.cour_des_comptes_extract import ReportInput
from .transforms.cour_des_comptes_extract import build_candidates as build_mention_candidates
from .transforms.legifrance_candidates import (
    CANDIDATES_PATH as ATTRIBUTION_CANDIDATES_PATH,
)
from .transforms.legifrance_candidates import (
    SOURCE_ID as LEGIFRANCE_SOURCE_ID,
)
from .transforms.legifrance_candidates import (
    extract_attribution_candidates,
    write_candidates,
)

app = typer.Typer(help="Registry-driven ingestion pipeline.")

# Resolution rate below this fails the run (CI gate). Matches the Phase-0.5 spike's RESOLVE_MIN.
RESOLVE_RATE_MIN = 0.5

# Coverage floor for `make coverage` (FSC-56). The acceptance target is ≥90% (incremental curation);
# this floor guards against a regression below the 66% machine-seeded `auto` baseline.
COVERAGE_RATE_MIN = 0.66

# Match-rate floor for `attributions-candidates` (FSC-66): below this, the décret→ministry linker is
# under-resolving and the run fails loud so a degraded extraction is never silently accepted.
ATTRIBUTION_MATCH_RATE_MIN = 0.5

# Match-rate floor for `extract-mentions` (FSC-67): same intent for the report→entity linker.
MENTION_MATCH_RATE_MIN = 0.5

# recherche-entreprises politeness (curation): the published limit is ~7 req/s. Same values the
# spike names (RATE_LIMIT_SLEEP / SEARCH_PAGE_SIZE) — kept here so the CLI is self-contained.
_RECHERCHE_RATE_LIMIT_S = 0.15
_RECHERCHE_PAGE_SIZE = 10

# Default crosswalk maintainer stamped on a regenerated file (shared by resolve-seed + curate).
_DEFAULT_MAINTAINER = "contact@cartographie-fonds-publics.fr"


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


def _select_ingest_targets(only: list[str] | None, all_sources: bool) -> list[Source]:
    """Resolve which registry sources to ingest.

    Default: the curated load set (``ALL_SOURCE_IDS`` — exactly what ``make load`` consumes from
    snapshots). ``--only`` selects exact ids (fails loud on an unknown id); ``--all-sources`` walks
    the whole registry (useful with ``--discover-only`` to smoke-test every source's discovery).
    The editorial sources are *not* in the default: they curate from reviewed YAML, so their
    snapshot is provenance-only — ingest them explicitly with ``--only`` if you want it.
    """
    registry = {s.id: s for s in sources()}
    if only:
        unknown = [sid for sid in only if sid not in registry]
        if unknown:
            raise typer.BadParameter(f"unknown source id(s): {', '.join(unknown)}")
        return [registry[sid] for sid in only]
    if all_sources:
        return list(registry.values())
    return [registry[sid] for sid in ALL_SOURCE_IDS if sid in registry]


def _describe_resolved(resolved: dict[str, Any]) -> str:
    """A short, connector-agnostic description of what discovery resolved (for the run log)."""
    for key in ("title", "slug", "dataset_id", "resource_url", "endpoint", "source_ref"):
        value = resolved.get(key)
        if value:
            return f"{key}={value!r}"
    return f"keys={sorted(resolved)}"


def _run_ingest_source(connector: Connector, source: Source, *, discover_only: bool) -> str:
    """Run one source's pipeline; return a human detail. Raises on any stage failure.

    ``discover_only`` stops after discovery (a dry-run that resolves the live dataset without a
    download or snapshot — the cheap "what resolves?" probe). Validation is gated on the registry's
    explicit ``schema.validate`` opt-in (only DECP today); a ``None`` ref makes validate a no-op.
    """
    resolved = connector.discover(source.raw)
    if discover_only:
        return f"discovered {_describe_resolved(resolved)}"
    raw = connector.extract(resolved)
    connector.validate(raw, source.schema_ref if source.schema_validate else None)
    path = connector.snapshot(raw, source.id)
    return f"snapshot {path} ({len(raw):,} bytes)"


@app.command()
def ingest(
    only: Annotated[
        list[str] | None,
        typer.Option("--only", help="Ingest only these source id(s) (repeatable)."),
    ] = None,
    all_sources: Annotated[
        bool,
        typer.Option("--all-sources", help="Ingest every registry source, not just the load set."),
    ] = False,
    discover_only: Annotated[
        bool,
        typer.Option(
            "--discover-only", help="Resolve each source's dataset; do not extract/snapshot."
        ),
    ] = False,
) -> None:
    """Run discover → extract → validate → snapshot for the curated load sources (FSC-38).

    Routing is **all-or-nothing**: every target is resolved to a connector *before* any network
    side effect, so an unroutable source aborts the run before the first snapshot is written. Each
    source is then ingested independently (``write_snapshot`` advances its ``latest.json`` pointer
    atomically), and a per-source ok/skipped/failed summary is printed. The curated load
    (``load`` / ``make load``) is a separate, cross-source, provenance-scoped step run afterwards.
    Exits nonzero if any source failed.
    """
    targets = _select_ingest_targets(only, all_sources)

    routed: list[tuple[Source, Connector]] = []
    unroutable: list[str] = []
    for s in targets:
        try:
            routed.append((s, get_connector(s)))
        except UnknownPlatformError as exc:
            unroutable.append(f"{s.id}: {exc}")
    if unroutable:
        for line in unroutable:
            typer.echo(f"  UNROUTABLE {line}", err=True)
        typer.echo(
            f"[ingest] {len(unroutable)} source(s) cannot be routed to a connector — aborting "
            "before any extract.",
            err=True,
        )
        raise typer.Exit(code=1)

    ok = skipped = failed = 0
    for s, connector in routed:
        editorial = s.id in EDITORIAL_SOURCE_IDS
        # A credential-gated connector (PISTE) fails loud without its secret; treat absence as a
        # skip — the curated graph still renders the reviewed editorial YAML (golden rule #5).
        if not discover_only and not getattr(connector, "has_credentials", True):
            typer.echo(f"  SKIP {s.id}: credentials absent (editorial YAML fallback)")
            skipped += 1
            continue
        try:
            detail = _run_ingest_source(connector, s, discover_only=discover_only)
            typer.echo(f"  OK   {s.id} ({s.layer}): {detail}")
            ok += 1
        except (SnapshotError, UnsupportedFormatError) as exc:
            # A non-tabular editorial resource (e.g. the Cour des comptes PDF) can't be snapshotted;
            # its transform reads reviewed YAML, so this is a skip, not a failure.
            if editorial:
                typer.echo(f"  SKIP {s.id}: non-tabular resource — {exc}", err=True)
                skipped += 1
            else:
                typer.echo(f"  FAIL {s.id}: {exc}", err=True)
                failed += 1
        except Exception as exc:  # noqa: BLE001 — report any source failure and keep going
            typer.echo(f"  FAIL {s.id}: {type(exc).__name__}: {exc}", err=True)
            failed += 1

    typer.echo(f"[ingest] {ok} ok, {skipped} skipped, {failed} failed (of {len(routed)} routed)")
    if failed:
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
    maintainer: Annotated[str, typer.Option(help="File maintainer.")] = _DEFAULT_MAINTAINER,
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


@app.command(name="demo-seed-emit")
def demo_seed_emit(
    out: Annotated[Path, typer.Option(help="Demo seed SQL file to write.")] = DEMO_SQL_PATH,
) -> None:
    """Regenerate the ILLUSTRATIVE demo seed (supabase/demo_seed.sql) — FSC-50…53.

    A design-scale dev/preview slice (operators across all four levels + illustrative funds /
    delegates / participation flows + multi-year budgets + contracts) so the redesigned screens
    render rich data locally before the funding-flow ingestion lands. Generated — edit
    `ingestion.demo_seed`, never the SQL; a golden test fails loud on drift. DEV/PREVIEW ONLY.
    """
    written = emit_demo_sql(out)
    typer.echo(f"[demo-seed-emit] wrote {written}")


# The curated source sets the `load` command can render, by `--scope`. Defined in ingestion.load:
# `etat-central` (Phase 1 default), `all` (whole four-layer perimeter), `editorial` (the opt-in
# attributions/mentions layers, which curate from reviewed YAML — see _empty_rows below).
_LOAD_SCOPES: dict[str, tuple[str, ...]] = {
    "etat-central": ETAT_CENTRAL_SOURCE_IDS,
    "all": ALL_SOURCE_IDS,
    "editorial": EDITORIAL_SOURCE_IDS,
}


def _empty_rows(_source_id: str) -> tuple[list[str], list[dict[str, str]]]:
    """A no-snapshot (headers, rows) reader for editorial sources.

    Their transforms curate from reviewed YAML (data/attributions, data/mentions) and ignore the
    snapshot rows, so the editorial load needs no snapshot — feed empty rows instead of requiring
    one that `ingest` does not write for them.
    """
    return [], []


@app.command()
def load(
    out: Annotated[
        Path, typer.Option(help="Load SQL file to write (then applied by `make load`).")
    ] = LOAD_SQL_PATH,
    scope: Annotated[
        str,
        typer.Option(help="Curated source set to load: etat-central | all | editorial."),
    ] = "etat-central",
    only: Annotated[
        list[str] | None,
        typer.Option(
            "--only",
            help="Load exactly these snapshot-backed source id(s), overriding --scope. Use when a "
            "source in --scope has no live data yet (e.g. an upstream-deprecated dataset).",
        ),
    ] = None,
    snapshot_root: Annotated[
        Path | None, typer.Option(help="Snapshot root (defaults to CFP_SNAPSHOT_ROOT).")
    ] = None,
    allow_empty: Annotated[
        bool,
        typer.Option(
            help="Allow a source that produced 0 rows (a reload would delete its rows). Off by "
            "default — fail loud rather than wipe the graph from an empty/broken snapshot."
        ),
    ] = False,
) -> None:
    """Render the curated load SQL from the latest snapshots; print a load summary.

    ``--scope`` selects the source set: ``etat-central`` (default, Phase 1), ``all`` (the whole
    four-layer perimeter), or ``editorial`` (the attributions/mentions layers). ``--only`` overrides
    it with an explicit list of snapshot-backed sources — the escape hatch when a ``--scope all``
    source has no live data yet (an upstream-deprecated dataset) so the available layers still load.
    Emits SQL only — `make load` pipes it to psql via the service-role ``DATABASE_URL`` (mirroring
    `seed-emit` vs `make seed`). The load is idempotent and **provenance-scoped**: entities upsert
    on SIREN; edges/budget_facts rebuild per source (delete-by-provenance then insert), so a reload
    replaces exactly this load's sources and never touches another source's rows. Curated rows only
    — raw extracts stay as Parquet snapshots (golden rule #6).
    """
    if only:
        source_ids: tuple[str, ...] = tuple(only)
        read_rows = None  # --only is for snapshot-backed sources; editorial goes via --scope
    else:
        scoped = _LOAD_SCOPES.get(scope)
        if scoped is None:
            raise typer.BadParameter(
                f"unknown scope {scope!r}; choose from {', '.join(sorted(_LOAD_SCOPES))}"
            )
        source_ids = scoped
        # Editorial sources curate from reviewed YAML and ignore snapshot rows; feed an empty reader
        # so the load needs no snapshot for them (ingest does not snapshot them by default).
        read_rows = _empty_rows if scope == "editorial" else None
    root = snapshot_root if snapshot_root is not None else SNAPSHOT_ROOT
    written, bundle = emit_load_sql(
        out, source_ids=source_ids, snapshot_root=root, read_rows=read_rows, allow_empty=allow_empty
    )
    typer.echo(load_summary(bundle))
    typer.echo(f"[load] wrote {written}")


@app.command(name="attributions-candidates")
def attributions_candidates(
    out: Annotated[
        Path, typer.Option(help="Candidate backlog YAML to write.")
    ] = ATTRIBUTION_CANDIDATES_PATH,
    min_match_rate: Annotated[
        float, typer.Option(help="Exit nonzero below this décret→ministry match rate.")
    ] = ATTRIBUTION_MATCH_RATE_MIN,
) -> None:
    """Discover décrets d'attribution via PISTE/Légifrance and write a review backlog (FSC-66).

    Runs the live discover→extract loop (needs the operator-provisioned PISTE OAuth2 secret), links
    each décret to a ministry by deterministic title-token matching, and writes the candidates to a
    human-review backlog — **never auto-published**. Promotion into the reviewed
    ``data/attributions/ministres.yaml`` is a manual step (see data/attributions/README.md). Exits
    nonzero below the match-rate floor.
    """
    connector = RestConnector()
    if not connector.has_credentials:
        raise typer.BadParameter(
            "PISTE credentials absent — set PISTE_CLIENT_ID / PISTE_CLIENT_SECRET (a free, "
            "operator-provisioned account) to run the live extraction. Phase-1 attributions still "
            "render from the reviewed editorial YAML in the meantime."
        )
    source = get_source(LEGIFRANCE_SOURCE_ID).raw
    resolved = connector.discover(source)
    raw = connector.extract(resolved)
    decrees = json.loads(raw).get(EXTRACT_ENVELOPE_KEY, [])
    result = extract_attribution_candidates(decrees, ministries=load_ministries())
    write_candidates(result, out)
    rate = result.report["match_rate"]
    rate_str = f"{rate:.0%}" if rate is not None else "n/a"
    typer.echo(
        f"[attributions-candidates] {result.report['matched']}/{result.report['total']} décrets "
        f"linked (match rate {rate_str}); {result.report['unresolved']} -> backlog {out}"
    )
    # A zero-candidate run (rate is None) must fail loud — a degraded extraction is never a pass.
    if result.report["total"] == 0:
        typer.echo("[attributions-candidates] no décrets discovered — nothing to link", err=True)
        raise typer.Exit(code=1)
    if rate is not None and rate < min_match_rate:
        typer.echo(
            f"[attributions-candidates] match rate {rate:.0%} < {min_match_rate:.0%} floor",
            err=True,
        )
        raise typer.Exit(code=1)


def _load_report_specs(path: Path) -> list[dict[str, Any]]:
    """Read a YAML list of report specs (url/report_ref/report_date/mention_type[/license]).

    Fields may be optional/null, but each entry must be a mapping carrying a non-empty ``url`` —
    validated here so a malformed reports file fails with an actionable CLI error, not a later
    ``KeyError`` mid-fetch.
    """
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    specs = data.get("reports") if isinstance(data, dict) else None
    if not isinstance(specs, list) or not specs:
        raise typer.BadParameter(f"{path}: expected a non-empty 'reports' list")
    for index, spec in enumerate(specs):
        if not isinstance(spec, dict) or not str(spec.get("url") or "").strip():
            raise typer.BadParameter(
                f"{path}: reports[{index}] must be a mapping with a non-empty 'url'"
            )
    return specs


@app.command(name="extract-mentions")
def extract_mentions(
    reports: Annotated[
        Path, typer.Option(help="YAML of report specs (url/report_ref/report_date/mention_type).")
    ],
    out: Annotated[
        Path, typer.Option(help="Candidate backlog YAML to write.")
    ] = MENTION_CANDIDATES_PATH,
    crosswalk: Annotated[Path, typer.Option(help="Crosswalk YAML path.")] = CROSSWALK_PATH,
    min_match_rate: Annotated[
        float, typer.Option(help="Exit nonzero below this report→entity match rate.")
    ] = MENTION_MATCH_RATE_MIN,
) -> None:
    """Parse Cour des comptes report PDFs → entity mention candidates → review backlog (FSC-67).

    Downloads each report PDF directly (not the snapshot layer — PDFs are non-tabular, FSC-38),
    extracts text, links named entities to a SIREN via the reviewed crosswalk + ministry reference,
    and writes the candidates to a human-review backlog — **never auto-published**. Promotion into
    ``data/mentions/cour_des_comptes.yaml`` is manual. Exits nonzero below the match-rate floor.
    """
    specs = _load_report_specs(reports)
    inputs = [
        ReportInput(
            url=str(spec["url"]),
            report_ref=str(spec.get("report_ref") or ""),
            report_date=spec.get("report_date"),
            mention_type=str(spec.get("mention_type") or "rapport"),
            pdf_bytes=fetch_pdf(str(spec["url"])),
            license=spec.get("license"),
        )
        for spec in specs
    ]
    result = build_mention_candidates(
        inputs,
        crosswalk_entries=load_entries(crosswalk),
        ministry_entries=load_ministries(),
    )
    write_mention_candidates(result, out)
    rate = result.report["match_rate"]
    rate_str = f"{rate:.0%}" if rate is not None else "n/a"
    typer.echo(
        f"[extract-mentions] {result.report['candidates_resolved']}/"
        f"{result.report['candidates_total']} candidates resolved (match rate {rate_str}); "
        f"{result.report['reports_with_candidates']}/{result.report['reports_total']} reports "
        f"with a hit -> backlog {out}"
    )
    # A zero-candidate run (rate is None) must fail loud — a degraded extraction is never a pass.
    if result.report["candidates_total"] == 0:
        typer.echo(
            "[extract-mentions] no candidates extracted — nothing matched the gazetteer", err=True
        )
        raise typer.Exit(code=1)
    if rate is not None and rate < min_match_rate:
        typer.echo(
            f"[extract-mentions] match rate {rate:.0%} < {min_match_rate:.0%} floor", err=True
        )
        raise typer.Exit(code=1)


@app.command()
def coverage(
    crosswalk: Annotated[Path, typer.Option(help="Crosswalk YAML path.")] = CROSSWALK_PATH,
    out: Annotated[Path, typer.Option(help="Report output path.")] = Path(
        "out/coverage_report.json"
    ),
    min_rate: Annotated[
        float, typer.Option(help="Exit nonzero below this resolved share.")
    ] = COVERAGE_RATE_MIN,
) -> None:
    """Report operator→SIREN coverage over the committed crosswalk (FSC-56 acceptance metric).

    Coverage is measured over **distinct operators**, not rows: resolved = the distinct SIRENs
    carried by `auto`/`reviewed` rows; the denominator adds the `pending` backlog (operators still
    needing a SIREN). Counting distinct SIRENs means clean-name seed/fixture aliases (which share
    a SIREN with a live `auto` row) never inflate the metric. `category` labels are excluded
    (unresolved by design). Target is ≥90% (curation is incremental — the `pending` backlog is the
    documented human-review queue); the floor guards against a regression below the `auto` baseline.
    """
    entries = load_entries(crosswalk)
    by_status: dict[str, int] = {}
    for entry in entries:
        by_status[entry.status.value] = by_status.get(entry.status.value, 0) + 1
    _accepted = (CrosswalkStatus.auto, CrosswalkStatus.reviewed)
    resolved_sirens = {e.siren for e in entries if e.status in _accepted and e.siren is not None}
    pending = by_status.get("pending", 0)
    total = len(resolved_sirens) + pending
    rate = (len(resolved_sirens) / total) if total else 0.0
    report = {
        "distinct_resolved_sirens": len(resolved_sirens),
        "pending_backlog": pending,
        "total_operators": total,
        "coverage_rate": rate,
        "by_status": by_status,
    }
    _write_report(report, out)
    typer.echo(
        f"[coverage] {len(resolved_sirens)}/{total} distinct operators carry a SIREN "
        f"(coverage {rate:.1%}); pending backlog {pending} -> {out}"
    )
    for status, count in sorted(by_status.items()):
        typer.echo(f"  {status}: {count}")
    if rate < min_rate:
        typer.echo(f"[coverage] coverage {rate:.1%} < {min_rate:.0%} floor", err=True)
        raise typer.Exit(code=1)


def _recherche_search_fn(client: httpx.Client, base_url: str, failures: list[str]) -> SearchFn:
    """A rate-limited recherche-entreprises search (registry-driven base URL, never hardcoded).

    A failed lookup is **recorded** in ``failures`` (not silently treated as "no match"), so a
    flaky API can't quietly leave operators ``pending`` without a signal — the caller reports the
    count and fails loud. The rate-limit sleep runs in ``finally`` (every call, success or error),
    so a burst of errors never bypasses the published ~7 req/s throttle.
    """

    def search(name: str) -> list[dict[str, object]]:
        try:
            resp = client.get(
                base_url, params={"q": name, "page": 1, "per_page": _RECHERCHE_PAGE_SIZE}
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return results if isinstance(results, list) else []
        except (httpx.HTTPError, ValueError):
            failures.append(name)
            return []
        finally:
            time.sleep(_RECHERCHE_RATE_LIMIT_S)

    return search


@app.command(name="curate-operators")
def curate_operators(
    crosswalk: Annotated[
        Path, typer.Option(help="Crosswalk YAML to curate (merge-aware).")
    ] = CROSSWALK_PATH,
    apply: Annotated[
        bool, typer.Option(help="Write the promotions (default: dry-run report only).")
    ] = False,
    reviewed_by: Annotated[str, typer.Option(help="reviewed_by stamp for promoted rows.")] = (
        "curate-operators"
    ),
    maintainer: Annotated[str, typer.Option(help="File maintainer.")] = _DEFAULT_MAINTAINER,
) -> None:
    """Promote `pending` operators to `reviewed` via the recherche-entreprises API (FSC-56).

    Accepts a SIREN only on a single, unambiguous, public-sector match (exact name / sigle /
    containment) — golden rule #5: never guess. Dry-run by default (reports what *would* move); pass
    ``--apply`` to write. `reviewed`/`category` curation is preserved; re-running is idempotent.
    Exits nonzero if any API lookup failed, so a flaky run is never mistaken for a clean backlog.
    """
    entries = load_entries(crosswalk)
    base_url = get_source("recherche_entreprises").raw.get("endpoint_hint")
    if not isinstance(base_url, str) or not base_url.strip():
        raise typer.BadParameter("recherche_entreprises source has no endpoint_hint base URL")
    reviewed_at = datetime.now(tz=UTC).date().isoformat()
    failures: list[str] = []
    with httpx.Client(headers={"User-Agent": "cfp-curate/0.1"}, timeout=20.0) as client:
        result = curate(
            entries,
            _recherche_search_fn(client, base_url.strip(), failures),
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
        )
    report = result.report
    action = "promoted" if apply else "would promote"
    typer.echo(
        f"[curate-operators] {action} {report['promoted_to_reviewed']} of {report['pending_in']} "
        f"pending; {report['still_pending']} remain in the backlog"
    )
    if apply:
        dump_entries(result.entries, crosswalk, maintainer=maintainer)
        typer.echo(f"[curate-operators] wrote {crosswalk}")
    else:
        typer.echo("[curate-operators] dry-run — pass --apply to write the promotions")
    if failures:
        typer.echo(
            f"[curate-operators] {len(failures)} API lookup(s) failed — results are partial; "
            "re-run to retry (a failed lookup is never treated as 'no match')",
            err=True,
        )
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
