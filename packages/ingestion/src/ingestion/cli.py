"""Ingestion CLI (stub). Commands: ingest, refresh, resolve, operators, budget, resolve-seed,
seed-emit."""

from __future__ import annotations

import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import httpx
import typer
import yaml
from core.crosswalk import CrosswalkStatus
from core.models import Entity, Level
from core.resolution import resolve_entities

from .connectors import Connector, UnknownPlatformError, get_connector
from .connectors.cour_des_comptes_pdf import fetch_pdf
from .connectors.rest import RestConnector
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
from .load import LOAD_SQL_PATH, emit_load_sql, load_summary
from .mentions_candidates_io import CANDIDATES_PATH as MENTION_CANDIDATES_PATH
from .mentions_candidates_io import write_candidates as write_mention_candidates
from .registry import Source, get_source, sources
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
        # TODO (FSC-38): connector.discover -> extract -> validate -> snapshot. The curated load
        # is a separate, cross-source step run after snapshots exist (`load` command / `make load`,
        # see ingestion.load), not folded into a per-source stage(); that keeps the rebuild
        # provenance-scoped and atomic. When this loop snapshots live, decide all-or-nothing routing
        # before any side effects.
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


@app.command()
def load(
    out: Annotated[
        Path, typer.Option(help="Load SQL file to write (then applied by `make load`).")
    ] = LOAD_SQL_PATH,
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
    """Render the curated État-central load SQL from the latest snapshots; print a load summary.

    Emits SQL only — `make load` pipes it to psql via the service-role ``DATABASE_URL`` (mirroring
    `seed-emit` vs `make seed`). The load is idempotent and **provenance-scoped**: entities upsert
    on SIREN; edges/budget_facts are rebuilt per source (delete-by-provenance then insert), so a
    reload replaces exactly this load's sources and never touches another source's rows. Curated
    rows only — raw extracts stay as Parquet snapshots (golden rule #6).
    """
    root = snapshot_root if snapshot_root is not None else SNAPSHOT_ROOT
    written, bundle = emit_load_sql(out, snapshot_root=root, allow_empty=allow_empty)
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
    decrees = json.loads(raw).get("texts", [])
    result = extract_attribution_candidates(decrees, ministries=load_ministries())
    write_candidates(result, out)
    rate = result.report["match_rate"]
    rate_str = f"{rate:.0%}" if rate is not None else "n/a"
    typer.echo(
        f"[attributions-candidates] {result.report['matched']}/{result.report['total']} décrets "
        f"linked (match rate {rate_str}); {result.report['unresolved']} -> backlog {out}"
    )
    if rate is not None and rate < min_match_rate:
        typer.echo(
            f"[attributions-candidates] match rate {rate:.0%} < {min_match_rate:.0%} floor",
            err=True,
        )
        raise typer.Exit(code=1)


def _load_report_specs(path: Path) -> list[dict[str, str]]:
    """Read a YAML list of report specs (url/report_ref/report_date/mention_type[/license])."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    specs = data.get("reports") if isinstance(data, dict) else None
    if not isinstance(specs, list) or not specs:
        raise typer.BadParameter(f"{path}: expected a non-empty 'reports' list")
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
