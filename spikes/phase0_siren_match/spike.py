#!/usr/bin/env python3
"""Phase-0 spike — prove the data join before building (FSC-19 risk gate).

It validates the two riskiest assumptions of the whole project:

1. **Registry-driven discovery** works: we can find the latest "jaune opérateurs"
   and DECP datasets via the data.gouv.fr /api/1 catalog *without any hardcoded slug*.
2. **SIREN is a usable join key**: State operators can be matched to public buyers
   AND suppliers in the procurement data (DECP). The headline outputs are operator
   **SIREN coverage** and the **SIREN match rate** — the #1 go/no-go indicators for
   the institutional graph.

Modes
-----
    python spike.py --sample      # offline, uses bundled fixtures (default for `make spike`)
    python spike.py               # live: discover, download, validate, snapshot, then MATCH

Live mode reuses the workspace packages end-to-end (``core.resolve`` for SIREN,
``ingestion.validation`` for fail-loud drift, ``ingestion.snapshot`` for the raw Parquet +
provenance). It therefore runs inside the uv workspace venv (``uv run``), not stdlib-only.
This spike is a *gate* for the Phase-1 connectors; it is not the connectors themselves.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from core.resolve import match_rate, normalize_siren
from ingestion.errors import SchemaResolutionError
from ingestion.registry import Source, get_source
from ingestion.snapshot import write_snapshot
from ingestion.validation import validate_extract

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
FIXTURES = HERE / "fixtures"
OUT_DIR = HERE / "out"

DEFAULT_API_BASE = "https://www.data.gouv.fr/api/1"
DEFAULT_MAX_RESOURCE_MB = 50
HTTP_TIMEOUT = 60.0
USER_AGENT = "cfp-phase0-spike"

# Go/no-go thresholds. Coverage is the dominant Phase-0 risk (can we get a SIREN at all);
# the match rate is supporting evidence that the SIREN actually wires into the graph.
COVERAGE_MIN = 0.5
MATCH_MIN = 0.5


class SpikeAbort(Exception):
    """A live run could not complete (network down, no dataset, no bounded resource).

    Carries a process exit code so ``main`` can translate it without leaking a traceback.
    """

    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


# --------------------------------------------------------------------------- #
# SIREN helpers (reuse core.resolve; add the canonical SIRET -> SIREN reduction)
# --------------------------------------------------------------------------- #
def to_siren(value: str | None) -> str | None:
    """Return a 9-digit SIREN from a SIREN *or* SIRET value, else None.

    DECP identifies parties by SIRET (14 digits) as often as by SIREN (9). A SIRET is a
    SIREN plus a 5-digit establishment number (NIC), so its SIREN is the first 9 digits —
    a definition, not a guess. We still defer to ``core.resolve.normalize_siren`` for the
    final 9-digit validation.
    """
    siren = normalize_siren(value)
    if siren:
        return siren
    if value:
        digits = re.sub(r"\D", "", str(value))
        if len(digits) == 14:
            return normalize_siren(digits[:9])
    return None


def ensure_utf8(raw: bytes) -> tuple[bytes, str]:
    """Return ``(utf8_bytes, source_encoding)``, transcoding French open data if needed.

    The Jaune opérateurs CSV ships as cp1252/latin-1, not UTF-8 — and the snapshot harness
    (duckdb) only reads UTF-8. Transcoding to UTF-8 at the boundary keeps the harness untouched
    while leaving digit columns (SIREN, leading zeros) byte-identical. The original encoding is
    recorded in the run summary so Phase-1 connectors can declare it explicitly.
    """
    try:
        raw.decode("utf-8")
        return raw, "utf-8"
    except UnicodeDecodeError:
        pass
    for encoding in ("cp1252", "latin-1"):  # latin-1 maps every byte, so this always resolves
        try:
            return raw.decode(encoding).encode("utf-8"), encoding
        except UnicodeDecodeError:
            continue
    return raw, "unknown"


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------- #
# Offline mode: compute the SIREN match rate from fixtures
# --------------------------------------------------------------------------- #
def run_sample() -> float:
    print("=== Phase-0 spike — OFFLINE sample ===\n")

    operators = _read_csv(FIXTURES / "operateurs_sample.csv")
    contracts = _read_csv(FIXTURES / "decp_sample.csv")

    op_sirens = {s for r in operators if (s := normalize_siren(r.get("siren")))}
    buyer_sirens = {s for r in contracts if (s := normalize_siren(r.get("acheteur_siren")))}

    total_ops = len(operators)
    resolvable = len(op_sirens)  # operators that actually carry a SIREN
    matched = op_sirens & buyer_sirens  # operators found as public buyers in DECP

    coverage = resolvable / total_ops if total_ops else 0.0
    rate = len(matched) / resolvable if resolvable else 0.0

    print(f"Operators (rows)............... {total_ops}")
    print(f"  with a usable SIREN.......... {resolvable}  ({coverage:.0%} coverage)")
    print(f"  matched to a DECP buyer...... {len(matched)}")
    print(f"\n>>> SIREN MATCH RATE (resolvable): {rate:.0%}")
    print(f">>> SIREN MATCH RATE (all rows):   {len(matched) / total_ops:.0%}\n")

    # Build a tiny graph: operator --delegates--> supplier (titulaire), valued by montant.
    by_buyer: dict[str, list[dict]] = {}
    for c in contracts:
        b = normalize_siren(c.get("acheteur_siren"))
        if b:
            by_buyer.setdefault(b, []).append(c)

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for op in operators:
        siren = normalize_siren(op.get("siren"))
        if siren not in matched:
            continue
        nodes[siren] = {"siren": siren, "name": op["operateur"], "level": "state"}
        for c in by_buyer.get(siren, []):
            sup = normalize_siren(c.get("titulaire_siren")) or f"unknown:{c.get('titulaire_nom')}"
            nodes[sup] = {"siren": sup, "name": c.get("titulaire_nom"), "level": "delegated"}
            edges.append(
                {
                    "source_siren": siren,
                    "target_siren": sup,
                    "type": "delegates",
                    "amount_eur": float(c.get("montant") or 0) or None,
                    "nature": c.get("nature"),
                    "provenance": "decp_commande_publique",
                }
            )

    OUT_DIR.mkdir(exist_ok=True)
    out_file = OUT_DIR / "phase0_graph.json"
    out_file.write_text(
        json.dumps({"nodes": list(nodes.values()), "edges": edges}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    rel = out_file.relative_to(REPO_ROOT)
    print(f"Sample graph: {len(nodes)} nodes / {len(edges)} edges -> {rel}")

    verdict = "VIABLE" if rate >= 0.5 else "NEEDS-WORK (improve SIREN coverage)"
    print("\nInterpretation: a real graph edge was built from public money to a private")
    print(f"supplier, keyed on SIREN. Graph viability on this sample: {verdict}.")
    return rate


# --------------------------------------------------------------------------- #
# Live mode — discovery helpers (registry-driven, no hardcoded slug)
# --------------------------------------------------------------------------- #
def query_from_strategy(source: Source) -> str:
    """Extract the catalog search query from the registry discovery strategy.

    The strategy reads e.g. ``search_datasets(query='jaune opérateurs de l'État'); ...`` —
    a *search query*, never a frozen slug. We parse the quoted phrase so the query stays in
    the registry (the single source of truth), not in code.
    """
    strategy = str(source.discovery.get("strategy", ""))
    match = re.search(r"search_datasets\(\s*(?:query\s*=\s*)?['\"](.+?)['\"]\s*\)", strategy)
    if not match:
        raise SpikeAbort(
            f"Could not derive a search query from {source.id!r} discovery.strategy: "
            f"{strategy!r}. Fix the registry strategy string."
        )
    return match.group(1)


def _latest_by_year(datasets: list[dict]) -> dict | None:
    """Pick the dataset whose title carries the most recent 4-digit year."""
    best, best_year = None, -1
    for d in datasets:
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", d.get("title", ""))]
        year = max(years) if years else 0
        if year > best_year:
            best, best_year = d, year
    return best


def discover_dataset(client: httpx.Client, api_base: str, query: str, limit: int) -> dict:
    """Resolve the latest dataset for a query via the data.gouv.fr catalog. No frozen slug."""
    try:
        resp = client.get(
            f"{api_base}/datasets/",
            params={"q": query, "page_size": limit},
            follow_redirects=True,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SpikeAbort(
            f"Catalog discovery failed for query {query!r} ({exc}). "
            f"Run the offline proof instead:  python spike.py --sample"
        ) from exc

    datasets = payload.get("data", [])
    if not datasets:
        raise SpikeAbort(f"No datasets returned for query {query!r}. Broaden it or run --sample.")
    return _latest_by_year(datasets) or datasets[0]


def select_csv_resource(dataset: dict) -> dict:
    """Pick the PRIMARY CSV resource — the largest by catalog filesize.

    The main data file is the largest; small CSVs in a consolidated dataset are annexes
    (e.g. DECP ships ``decp.csv`` (~2 GB) alongside ``probabilites-naf-cpv.csv`` and
    ``statistiques-sources.csv``). Picking the smallest would silently grab an annex. The
    download is bounded separately by a head-sample, so size here is a *selection* signal only.
    """
    csvs = [r for r in dataset.get("resources", []) if str(r.get("format", "")).lower() == "csv"]
    if not csvs:
        raise SpikeAbort(f"No CSV resource in dataset {dataset.get('title')!r}.")
    return max(csvs, key=lambda r: (r.get("filesize") or 0, r.get("last_modified") or ""))


def download_head(client: httpx.Client, url: str, max_bytes: int) -> tuple[bytes, bool]:
    """Stream up to ``max_bytes`` of a resource. Return ``(bytes, truncated)``.

    Keeps a giant dump (DECP's 2 GB consolidated CSV) bounded by sampling its head rather than
    failing. When truncated, the trailing partial line is dropped so the CSV parses cleanly.
    """
    try:
        with client.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            truncated = False
            for chunk in resp.iter_bytes():
                chunks.append(chunk)
                total += len(chunk)
                if total >= max_bytes:
                    truncated = True
                    break
    except httpx.HTTPError as exc:
        raise SpikeAbort(f"Download failed for {url} ({exc}).") from exc

    data = b"".join(chunks)
    if truncated:
        data = data[:max_bytes]
        cut = data.rfind(b"\n")
        if cut != -1:
            data = data[:cut]  # drop the dangling partial row
    return data, truncated


# --------------------------------------------------------------------------- #
# Live mode — CSV parsing + SIREN column detection
# --------------------------------------------------------------------------- #
def parse_csv_bytes(raw: bytes) -> tuple[list[str], list[dict]]:
    """Decode + parse a CSV extract, sniffing the delimiter (French open data favours ';')."""
    text = raw.decode("utf-8-sig", errors="replace")  # accents are irrelevant to digit columns
    sample = text[:8192]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    return (reader.fieldnames or []), rows


def column_by_name(headers: list[str], pattern: str) -> str | None:
    """First header matching ``pattern`` (case-insensitive), else None."""
    return next((h for h in headers if h and re.search(pattern, h, re.I)), None)


def column_by_values(headers: list[str], rows: list[dict], threshold: float = 0.5) -> str | None:
    """Header whose non-empty values are predominantly valid SIREN/SIRET — a content fallback."""
    best, best_frac = None, 0.0
    for header in headers:
        if not header:
            continue
        values = [r.get(header) for r in rows[:200]]
        nonempty = [v for v in values if v not in (None, "")]
        if not nonempty:
            continue
        frac = sum(1 for v in nonempty if to_siren(v)) / len(nonempty)
        if frac > best_frac:
            best, best_frac = header, frac
    return best if best_frac >= threshold else None


def role_id_columns(headers: list[str], role: str) -> list[str]:
    """DECP id columns for a role ('acheteur'/'titulaire'): prefer siren/siret, else an *id field.

    The fallback anchors on a trailing ``id`` (optionally numbered, e.g. ``titulaire_id_2``) so it
    matches ``acheteur_id`` / ``titulaire.id`` but NOT ``titulaire_typeIdentifiant`` (a label).
    """
    strong = [h for h in headers if h and re.search(rf"{role}.*(siren|siret)", h, re.I)]
    if strong:
        return strong
    return [h for h in headers if h and re.search(rf"{role}.*id(_\d+)?$", h, re.I)]


def collect_sirens(rows: list[dict], columns: list[str]) -> set[str]:
    """Normalised SIRENs across the given columns (SIRET reduced to SIREN)."""
    out: set[str] = set()
    for row in rows:
        for col in columns:
            siren = to_siren(row.get(col))
            if siren:
                out.add(siren)
    return out


# --------------------------------------------------------------------------- #
# Live mode — per-source extract (discover -> download -> validate -> snapshot)
# --------------------------------------------------------------------------- #
def extract_source(
    client: httpx.Client,
    source: Source,
    *,
    api_base: str,
    limit: int,
    max_bytes: int,
    snapshot_root: Path | None,
) -> dict[str, Any]:
    """Run the harness-backed extract for one registry source and return its artifacts."""
    query = query_from_strategy(source)
    print(f"[{source.id}] discovery query (from registry): {query!r}")
    dataset = discover_dataset(client, api_base, query, limit)
    print(f"[{source.id}] resolved millésime: {dataset.get('title')!r} (id={dataset.get('id')})")

    resource = select_csv_resource(dataset)
    url = resource["url"]
    full_mb = (resource.get("filesize") or 0) / 1_000_000
    print(f"[{source.id}] CSV resource: {resource.get('title')!r} (~{full_mb:.1f} MB)  {url}")
    downloaded, truncated = download_head(client, url, max_bytes)
    raw, source_encoding = ensure_utf8(downloaded)
    enc_note = "" if source_encoding == "utf-8" else f", transcoded from {source_encoding} -> utf-8"
    sample_note = "  [HEAD SAMPLE — file exceeds cap]" if truncated else ""
    print(f"[{source.id}] downloaded {len(downloaded):,} bytes{enc_note}{sample_note}")

    # Validate against the declared Table Schema. A real column drift fails loud
    # (SchemaValidationError propagates). A misconfigured ref (DECP currently points at the
    # portal root — FSC-16 follow-up) is a CONFIG fault, not drift: skip with a warning.
    validation_note = "no schema declared (skipped)"
    cell_warnings = 0
    try:
        report = validate_extract(raw, source_id=source.id, schema_ref=source.schema_ref)
        cell_warnings = report.cell_warning_count
        if report.skipped:
            validation_note = "no schema declared (skipped)"
        else:
            validation_note = f"validated OK ({cell_warnings} cell warning(s))"
    except SchemaResolutionError as exc:
        validation_note = f"schema ref not a usable TableSchema — validation skipped ({exc})"
        print(f"[{source.id}] ⚠ {validation_note}")

    snapshot_kwargs: dict[str, Any] = {} if snapshot_root is None else {"root": snapshot_root}
    snapshot_path = write_snapshot(
        raw,
        source_id=source.id,
        extracted_at=datetime.now(tz=UTC).isoformat(),
        source_ref=url,
        license=source.raw.get("license"),
        schema_ref=source.schema_ref,
        cell_warnings=cell_warnings,
        **snapshot_kwargs,
    )
    print(f"[{source.id}] snapshot -> {snapshot_path}")

    headers, rows = parse_csv_bytes(raw)
    return {
        "source_id": source.id,
        "dataset": {
            "id": dataset.get("id"),
            "title": dataset.get("title"),
            "slug": dataset.get("slug"),
            "page": dataset.get("page"),
        },
        "resource_url": url,
        "resource_full_mb": round(full_mb, 2),
        "sampled_head": truncated,
        "source_encoding": source_encoding,
        "snapshot_path": str(snapshot_path),
        "validation_note": validation_note,
        "headers": headers,
        "rows": rows,
    }


def _verdict(
    coverage: float,
    match_either: float,
    *,
    op_siren_column: str | None,
    decp_key_count: int,
) -> tuple[str, bool, str]:
    """Map the findings into a go/no-go string, an exit-ok flag, and an interpretation.

    The binding Phase-0 risk is whether the operators source carries SIREN at all. When it does
    not, the match is structurally 0 regardless of DECP — but the join key being present on the
    DECP side means the path is a CONDITIONAL go: add a name->SIREN crosswalk first.
    """
    decp_ready = decp_key_count > 0
    if op_siren_column is None:
        return (
            "CONDITIONAL GO (operators need a name->SIREN crosswalk)",
            False,
            "The operators (Jaune) list carries NO SIREN column, so direct SIREN coverage is 0% "
            f"and the match is structurally 0. The join key IS usable on the DECP side "
            f"({decp_key_count} distinct buyer/supplier SIRENs in the sample), and the offline "
            "sample proves the join works when SIRENs are present. REQUIRED Phase-1 prerequisite: "
            "resolve operator dénomination + tutelle -> SIREN via a reviewed crosswalk "
            "(SIRENE / annuaire de l'administration) before wiring operators into DECP.",
        )
    if coverage < COVERAGE_MIN:
        return (
            "NO-GO",
            False,
            f"Operator SIREN coverage is only {coverage:.0%} (< {COVERAGE_MIN:.0%}). Mitigation: "
            "complete SIRENs via a reviewed name-match crosswalk (dénomination + tutelle) against "
            "SIRENE before relying on the SIREN join.",
        )
    if not decp_ready:
        return (
            "NO-GO",
            False,
            f"Operators resolve to SIREN ({coverage:.0%}) but the DECP sample exposed no usable "
            "buyer/supplier SIREN — selection/format issue. Re-check the DECP resource.",
        )
    if match_either < MATCH_MIN:
        return (
            "GO (qualified)",
            True,
            f"Operator SIREN coverage is strong ({coverage:.0%}); the match against a bounded DECP "
            f"sample is {match_either:.0%}. Expected — not every operator procures within the "
            "sampled head. Phase 1's full-DECP join should raise it.",
        )
    return (
        "GO",
        True,
        f"Operators resolve to SIREN ({coverage:.0%} coverage) and join into DECP "
        f"({match_either:.0%} appear as a buyer or supplier). The institutional graph is viable.",
    )


def run_live(
    *,
    api_base: str = DEFAULT_API_BASE,
    limit: int = 20,
    max_resource_mb: int = DEFAULT_MAX_RESOURCE_MB,
    snapshot_root: Path | None = None,
    out_dir: Path = OUT_DIR,
) -> dict[str, Any]:
    """Live end-to-end: discover, download, validate, snapshot, then compute the SIREN match.

    Returns a summary dict (also written to ``out_dir/phase0_live_summary.json``). Raises
    ``SpikeAbort`` if the run cannot complete (so ``main`` controls the process exit code).
    """
    print("=== Phase-0 spike — LIVE end-to-end (registry-driven) ===\n")
    max_bytes = max_resource_mb * 1_000_000

    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
        operators = extract_source(
            client,
            get_source("operateurs_etat"),
            api_base=api_base,
            limit=limit,
            max_bytes=max_bytes,
            snapshot_root=snapshot_root,
        )
        print()
        decp = extract_source(
            client,
            get_source("decp_commande_publique"),
            api_base=api_base,
            limit=limit,
            max_bytes=max_bytes,
            snapshot_root=snapshot_root,
        )

    # --- SIREN match -------------------------------------------------------- #
    op_col = column_by_name(operators["headers"], r"siren") or column_by_values(
        operators["headers"], operators["rows"]
    )
    total_ops = len(operators["rows"])
    op_sirens = collect_sirens(operators["rows"], [op_col]) if op_col else set()
    coverage = len(op_sirens) / total_ops if total_ops else 0.0

    buyer_cols = role_id_columns(decp["headers"], "acheteur")
    supplier_cols = role_id_columns(decp["headers"], "titulaire")
    buyer_sirens = collect_sirens(decp["rows"], buyer_cols)
    supplier_sirens = collect_sirens(decp["rows"], supplier_cols)
    either = buyer_sirens | supplier_sirens

    m_buyers = match_rate(op_sirens, buyer_sirens)
    m_suppliers = match_rate(op_sirens, supplier_sirens)
    m_either = match_rate(op_sirens, either)
    verdict, exit_ok, interpretation = _verdict(
        coverage, m_either, op_siren_column=op_col, decp_key_count=len(either)
    )

    print("\n--- SIREN MATCH ---")
    print(f"Operators (rows).................. {total_ops}")
    print(f"  SIREN column .................. {op_col!r}")
    print(f"  with a usable SIREN ........... {len(op_sirens)}  ({coverage:.0%} coverage)")
    print(
        f"DECP sample (rows) ............... {len(decp['rows'])}"
        f"{'  [head sample]' if decp['sampled_head'] else ''}"
    )
    print(f"  buyer id column(s) ............ {buyer_cols}  -> {len(buyer_sirens)} distinct SIREN")
    print(f"  supplier id column(s) ......... {supplier_cols}  -> {len(supplier_sirens)} distinct")
    print(f"\n>>> MATCH vs DECP buyers ......... {m_buyers:.0%}")
    print(f">>> MATCH vs DECP suppliers ...... {m_suppliers:.0%}")
    print(f">>> MATCH vs DECP (buyer|supplier) {m_either:.0%}")
    print(f"\n>>> VERDICT: {verdict}")
    print(interpretation)

    summary = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "api_base": api_base,
        "max_resource_mb": max_resource_mb,
        "operators": {
            "dataset": operators["dataset"],
            "resource_url": operators["resource_url"],
            "resource_full_mb": operators["resource_full_mb"],
            "sampled_head": operators["sampled_head"],
            "source_encoding": operators["source_encoding"],
            "snapshot_path": operators["snapshot_path"],
            "validation": operators["validation_note"],
            "rows": total_ops,
            "siren_column": op_col,
            "resolvable": len(op_sirens),
            "coverage": coverage,
        },
        "decp": {
            "dataset": decp["dataset"],
            "resource_url": decp["resource_url"],
            "resource_full_mb": decp["resource_full_mb"],
            "sampled_head": decp["sampled_head"],
            "source_encoding": decp["source_encoding"],
            "snapshot_path": decp["snapshot_path"],
            "validation": decp["validation_note"],
            "rows": len(decp["rows"]),
            "buyer_columns": buyer_cols,
            "supplier_columns": supplier_cols,
            "distinct_buyer_sirens": len(buyer_sirens),
            "distinct_supplier_sirens": len(supplier_sirens),
        },
        "match_rate": {"buyers": m_buyers, "suppliers": m_suppliers, "either": m_either},
        "verdict": verdict,
        "exit_ok": exit_ok,
        "interpretation": interpretation,
        "caveats": [
            "DECP match is computed against a bounded HEAD SAMPLE of the consolidated CSV, "
            "not all of DECP (the full file is ~2 GB).",
            "DECP parties are identified by SIRET; SIREN is its first 9 digits (canonical).",
            "DECP schema ref points at the portal root (FSC-16 follow-up) — real TableSchema "
            "validation is pending; the extract was still snapshotted with provenance.",
            "French open-data CSVs ship as cp1252/latin-1; the spike transcodes to UTF-8 at the "
            "boundary so the (UTF-8-only) snapshot harness can persist them.",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "phase0_live_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nMachine summary -> {summary_path}")
    return summary


# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="Phase-0 spike: SIREN join + discovery.")
    parser.add_argument("--sample", action="store_true", help="offline mode using fixtures")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="data.gouv.fr API base")
    parser.add_argument("--limit", type=int, default=20, help="datasets to fetch (live mode)")
    parser.add_argument(
        "--max-resource-mb",
        type=int,
        default=DEFAULT_MAX_RESOURCE_MB,
        help="cap a single downloaded CSV resource (keeps DECP bounded)",
    )
    args = parser.parse_args()

    if args.sample:
        rate = run_sample()
        sys.exit(0 if rate >= 0.5 else 1)

    try:
        summary = run_live(
            api_base=args.api_base, limit=args.limit, max_resource_mb=args.max_resource_mb
        )
    except SpikeAbort as exc:
        print(f"[!] {exc}")
        sys.exit(exc.exit_code)
    sys.exit(0 if summary["exit_ok"] else 1)


if __name__ == "__main__":
    main()
