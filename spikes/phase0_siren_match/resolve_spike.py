#!/usr/bin/env python3
"""Phase-0.5 spike — measure the operator name->SIREN auto-resolution rate (FSC-48).

FSC-19 proved the SIREN join is sound but found the *Jaune opérateurs de l'État* list carries
NO SIREN (0% coverage on 431 rows). Before building the crosswalk (FSC-23) and the operators
connector (FSC-25), this spike answers one number: **how many of the ~430 operators can we
auto-resolve to a SIREN from their dénomination?** That converts FSC-19's CONDITIONAL GO into a
measured *proceed* vs *curate-first* decision and sizes the manual-curation backlog.

Resolver: the public **recherche-entreprises** API (SIRENE-backed, no token) — its base URL lives
in the registry (``recherche_entreprises`` source), never hardcoded. Matching is deliberately
conservative: only an *exact* normalized-name match is auto-accepted (golden rule #5 — never
guess). Everything ambiguous or unmatched is routed to a concrete crosswalk artifact that sizes
the FSC-23 backlog.

Modes
-----
    python resolve_spike.py --sample   # offline, bundled fixtures (`make spike-resolve`)
    python resolve_spike.py            # live: discover operators + DECP, resolve, report

Live mode reuses the FSC-19 harness end-to-end via ``spike`` (discover/extract/validate/snapshot)
and ``core.resolve`` (SIREN + name normalization). It runs inside the uv workspace venv.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import httpx
from core.resolve import normalize_name
from ingestion.registry import Source, get_source
from spike import (
    DEFAULT_API_BASE,
    DEFAULT_MAX_RESOURCE_MB,
    HTTP_TIMEOUT,
    OUT_DIR,
    REPO_ROOT,
    USER_AGENT,
    SpikeAbort,
    collect_sirens,
    column_by_name,
    extract_source,
    role_id_columns,
    to_siren,
)

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# Resolution rate >= this -> the crosswalk is mostly automatic (proceed). Below -> curate first.
RESOLVE_MIN = 0.5
RATE_LIMIT_SLEEP = 0.15  # ~7 req/s — the recherche-entreprises published limit
SEARCH_PAGE_SIZE = 10

# Operator-list column detection. The Jaune has TWO name columns: a category grouping
# ("Opérateur ou catégorie d'opérateurs", filled on every row) and a leaf operator name
# ("Opérateur de la catégorie", filled only when a category has named members). The operator
# name is coalesce(leaf, grouping): the leaf when present, else the grouping (a standalone
# operator). Picking either alone drops ~165 of 431 rows — hence two pattern sets + coalesce.
DENOM_PATTERNS = (
    r"op[eé]rateur de la cat",
    r"d[eé]nomination",
    r"raison.?sociale",
    r"op[eé]rateur",
    r"\bnom\b",
)
FALLBACK_PATTERNS = (r"op[eé]rateur ou", r"cat[eé]gorie d['’ ]?op")
TUTELLE_PATTERNS = (r"tutelle", r"mission.*programme", r"minist")


# Jaune entries are often "ACRONYM - Full legal name" (e.g. "IGN - Institut national de
# l'information géographique et forestière"), but SIRENE stores only the full legal name. We
# strip a leading "ACRONYM - " (spaces required around the dash, so hyphenated single names like
# "Météo-France" are untouched) and also test the bare full name. The accept rule stays *exact*
# normalized equality — this removes a known formatting artifact, it does not fuzzy-guess.
_ACRONYM_PREFIX = re.compile(r"^[0-9A-Za-zÀ-ÿ&.'’]{2,15}\s+[-–—]\s+(?P<rest>.+\S)$")


def _name_variants(denomination: str) -> list[str]:
    """The operator name plus its acronym-stripped form, when it carries an 'ACRONYM - ' prefix."""
    variants = [denomination]
    match = _ACRONYM_PREFIX.match(denomination.strip())
    if match:
        variants.append(match.group("rest"))
    return variants


# --------------------------------------------------------------------------- #
# Candidate inspection (recherche-entreprises result shape)
# --------------------------------------------------------------------------- #
def _candidate_names(candidate: dict) -> list[str | None]:
    """The name fields a SIRENE candidate may match on (full name + legal name)."""
    return [candidate.get("nom_complet"), candidate.get("nom_raison_sociale")]


def _is_public(candidate: dict) -> bool:
    """Soft public-sector signal: an administration flag, or a public legal category (4xxx/7xxx).

    INSEE *catégorie juridique* 4xxx (EPIC and the like) and 7xxx (État, EPA/EPST, collectivités)
    are the public-law forms. Used only to disambiguate equally-named candidates — never to
    accept a non-exact name (a tutelle-code -> entity map is deferred to FSC-23).
    """
    comp = candidate.get("complements") or {}
    if comp.get("est_administration") is True:
        return True
    nature = str(candidate.get("nature_juridique") or "")
    return nature[:1] in {"4", "7"}


def _best_ratio(target_keys: set[str], candidates: list[dict]) -> float:
    """Best difflib ratio of any operator-name variant against any candidate name — *descriptive*.

    Never feeds the accept decision; it just annotates near-misses so the FSC-23 backlog rows
    carry a confidence signal for the human reviewer.
    """
    best = 0.0
    for candidate in candidates:
        for name in _candidate_names(candidate):
            key = normalize_name(name)
            if key:
                best = max(best, max(SequenceMatcher(None, t, key).ratio() for t in target_keys))
    return round(best, 3)


def classify_operator(denomination: str, tutelle: str, candidates: list[dict]) -> dict[str, Any]:
    """Classify one operator against its SIRENE candidates into the 3 ambiguity tiers.

    - ``unique``  : exactly one distinct SIREN whose normalized name *equals* the operator's
                    (after the public-sector soft filter) -> auto-accepted.
    - ``multiple``: several exact-name SIRENs the soft filter can't reduce to one -> crosswalk.
    - ``none``    : no exact-name candidate -> crosswalk (with the best near-miss ratio).

    Never guesses: only exact normalized-name equality is ever accepted (golden rule #5).
    """
    target = normalize_name(denomination)
    targets = {normalize_name(v) for v in _name_variants(denomination)} - {""}
    by_siren: dict[str, dict] = {}
    if targets:
        for candidate in candidates:
            siren = to_siren(candidate.get("siren"))
            if siren and any(normalize_name(n) in targets for n in _candidate_names(candidate)):
                by_siren.setdefault(siren, candidate)

    top_ratio = _best_ratio(targets or {target}, candidates)
    exact_sirens = list(by_siren)

    chosen: str | None = None
    if len(exact_sirens) == 1:
        chosen, tier = exact_sirens[0], "unique"
    elif len(exact_sirens) > 1:
        public = [s for s, c in by_siren.items() if _is_public(c)]
        if len(public) == 1:
            chosen, tier = (
                public[0],
                "unique",
            )  # soft filter broke the tie to a single public entity
        else:
            tier = "multiple"
    else:
        tier = "none"

    return {
        "operateur": denomination,
        "tutelle": tutelle,
        "normalized_name": target,
        "tier": tier,
        "candidate_sirens": exact_sirens,
        "chosen_siren": chosen,
        "n_candidates": len(exact_sirens),
        "top_match_ratio": top_ratio,
    }


# --------------------------------------------------------------------------- #
# recherche-entreprises (registry-driven base URL, never hardcoded)
# --------------------------------------------------------------------------- #
def recherche_base_url(source: Source) -> str:
    """Read the recherche-entreprises base URL from the registry source. No hardcoded URL."""
    url = source.raw.get("endpoint_hint")
    if not isinstance(url, str) or not url.strip():
        raise SpikeAbort(
            f"Source {source.id!r} has no usable endpoint_hint base URL. Fix the registry entry."
        )
    return url.strip()


def search_entreprises(
    client: httpx.Client, base_url: str, name: str, *, page_size: int = SEARCH_PAGE_SIZE
) -> list[dict]:
    """Full-text search SIRENE via recherche-entreprises. Returns candidates (possibly empty)."""
    try:
        resp = client.get(base_url, params={"q": name, "page": 1, "per_page": page_size})
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SpikeAbort(f"recherche-entreprises query failed for {name!r} ({exc}).") from exc
    results = payload.get("results", [])
    return results if isinstance(results, list) else []


def _coalesce(row: dict, cols: list[str]) -> str:
    """First non-empty value across ``cols`` in priority order — the operator's name."""
    for col in cols:
        value = str(row.get(col) or "").strip()
        if value:
            return value
    return ""


def resolve_operators(
    client: httpx.Client,
    rows: list[dict],
    base_url: str,
    *,
    name_cols: list[str],
    tutelle_col: str | None,
) -> list[dict[str, Any]]:
    """Resolve every operator row (one rate-limited API call each) into a classified record."""
    records: list[dict[str, Any]] = []
    for row in rows:
        denom = _coalesce(row, name_cols)
        if not denom:
            continue  # no operator name in any name column
        tutelle = str(row.get(tutelle_col) or "").strip() if tutelle_col else ""
        candidates = search_entreprises(client, base_url, denom)
        records.append(classify_operator(denom, tutelle, candidates))
        if RATE_LIMIT_SLEEP:
            time.sleep(RATE_LIMIT_SLEEP)
    return records


# --------------------------------------------------------------------------- #
# DECP appearance loop (closes FSC-19's structural 0%)
# --------------------------------------------------------------------------- #
def decp_appearance(resolved_sirens: set[str], decp_rows: list[dict], headers: list[str]) -> dict:
    """Share of resolved operator SIRENs that appear as a DECP buyer or supplier."""
    buyer_cols = role_id_columns(headers, "acheteur")
    supplier_cols = role_id_columns(headers, "titulaire")
    buyers = collect_sirens(decp_rows, buyer_cols)
    suppliers = collect_sirens(decp_rows, supplier_cols)
    appearing = resolved_sirens & (buyers | suppliers)
    rate = len(appearing) / len(resolved_sirens) if resolved_sirens else 0.0
    return {
        "buyer_columns": buyer_cols,
        "supplier_columns": supplier_cols,
        "distinct_buyer_sirens": len(buyers),
        "distinct_supplier_sirens": len(suppliers),
        "appearing": sorted(appearing),
        "appearance_rate": rate,
    }


# --------------------------------------------------------------------------- #
# Aggregation + verdict + artifacts
# --------------------------------------------------------------------------- #
def _tally(records: list[dict]) -> dict[str, int]:
    tiers = {"unique": 0, "multiple": 0, "none": 0}
    for record in records:
        tiers[record["tier"]] += 1
    return tiers


def _resolve_verdict(rate: float, backlog_n: int) -> tuple[str, bool, str]:
    """Map the resolution rate into a proceed/curate-first verdict, an exit-ok flag, and prose."""
    if rate >= RESOLVE_MIN:
        return (
            "PROCEED TO PHASE 1",
            True,
            f"Auto-resolution rate {rate:.0%} ≥ {RESOLVE_MIN:.0%}: the operator name->SIREN "
            f"crosswalk is mostly automatic. The bounded manual backlog is {backlog_n} operators "
            "(ambiguous + unmatched) for FSC-23 to absorb.",
        )
    return (
        f"CURATE-FIRST — manual backlog: {backlog_n} operators",
        False,
        f"Auto-resolution rate {rate:.0%} < {RESOLVE_MIN:.0%}: most operators need reviewed "
        f"curation. The backlog is bounded at {backlog_n} of the ~430 operators; FSC-23 must "
        "absorb it before operators wire into DECP. The join key itself is not the blocker.",
    )


_CSV_FIELDS = (
    "operateur",
    "tutelle",
    "normalized_name",
    "tier",
    "candidate_sirens",
    "chosen_siren",
    "n_candidates",
    "top_match_ratio",
    "appears_in_decp",
)


def write_crosswalk_csv(records: list[dict], decp_sirens: set[str], out_dir: Path) -> Path:
    """Write one row per operator: tier, candidate SIREN(s), confidence, DECP appearance.

    The non-``unique`` rows ARE the FSC-23 backlog, made concrete and countable.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "operator_resolution.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for record in records:
            chosen = record["chosen_siren"]
            writer.writerow(
                {
                    "operateur": record["operateur"],
                    "tutelle": record["tutelle"],
                    "normalized_name": record["normalized_name"],
                    "tier": record["tier"],
                    "candidate_sirens": "|".join(record["candidate_sirens"]),
                    "chosen_siren": chosen or "",
                    "n_candidates": record["n_candidates"],
                    "top_match_ratio": record["top_match_ratio"],
                    "appears_in_decp": bool(chosen and chosen in decp_sirens),
                }
            )
    return path


def _summarize(records: list[dict], appearance: dict, **extra: Any) -> dict[str, Any]:
    tiers = _tally(records)
    total = len(records)
    rate = tiers["unique"] / total if total else 0.0
    backlog = tiers["multiple"] + tiers["none"]
    verdict, exit_ok, interpretation = _resolve_verdict(rate, backlog)
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "operators_evaluated": total,
        "resolution_rate": rate,
        "tiers": tiers,
        "manual_backlog": backlog,
        "decp_appearance_rate": appearance["appearance_rate"],
        "decp_appearing": len(appearance["appearing"]),
        "verdict": verdict,
        "exit_ok": exit_ok,
        "interpretation": interpretation,
        **extra,
    }


def _print_report(summary: dict, appearance: dict) -> None:
    tiers = summary["tiers"]
    print("\n--- OPERATOR name->SIREN RESOLUTION ---")
    print(f"Operators evaluated ............. {summary['operators_evaluated']}")
    print(f"  unique  (auto-resolved) ....... {tiers['unique']}")
    print(f"  multiple (ambiguous) .......... {tiers['multiple']}")
    print(f"  none    (unmatched) ........... {tiers['none']}")
    print(f"\n>>> RESOLUTION RATE ............. {summary['resolution_rate']:.0%}")
    print(f">>> MANUAL BACKLOG (FSC-23) ..... {summary['manual_backlog']} operators")
    print(
        f">>> OPERATOR->DECP APPEARANCE ... {appearance['appearance_rate']:.0%}"
        f"  ({len(appearance['appearing'])} of {tiers['unique']} resolved appear in DECP)"
    )
    print(f"\n>>> VERDICT: {summary['verdict']}")
    print(summary["interpretation"])


def detect_column(headers: list[str], patterns: tuple[str, ...]) -> str | None:
    """First header matching any pattern in priority order (leaf operator before category)."""
    for pattern in patterns:
        col = column_by_name(headers, pattern)
        if col:
            return col
    return None


# --------------------------------------------------------------------------- #
# Offline mode — deterministic, no network (default for `make spike-resolve`)
# --------------------------------------------------------------------------- #
def _display_path(path: Path) -> Path | str:
    """Repo-relative path when possible (pretty logs), else the absolute path (e.g. tmp dirs)."""
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run_sample(out_dir: Path = OUT_DIR) -> dict[str, Any]:
    """Resolve a tiny bundled operator list against a bundled SIRENE index — proves the tiers."""
    print("=== Phase-0.5 spike — OFFLINE sample (operator name->SIREN) ===\n")
    operators = _read_csv(FIXTURES / "operateurs_resolve_sample.csv")
    index: dict[str, list[dict]] = json.loads(
        (FIXTURES / "recherche_sample.json").read_text(encoding="utf-8")
    )
    contracts = _read_csv(FIXTURES / "decp_sample.csv")

    records = [
        classify_operator(row["operateur"], row.get("tutelle", ""), index.get(row["operateur"], []))
        for row in operators
    ]
    resolved = {r["chosen_siren"] for r in records if r["chosen_siren"]}
    decp_headers = list(contracts[0].keys()) if contracts else []
    appearance = decp_appearance(resolved, contracts, decp_headers)
    decp_sirens = collect_sirens(
        contracts, role_id_columns(decp_headers, "acheteur")
    ) | collect_sirens(contracts, role_id_columns(decp_headers, "titulaire"))

    csv_path = write_crosswalk_csv(records, decp_sirens, out_dir)
    summary = _summarize(records, appearance, mode="sample")
    _print_report(summary, appearance)
    print(f"\nCrosswalk artifact -> {_display_path(csv_path)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "phase0_5_resolution_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


# --------------------------------------------------------------------------- #
# Live mode — discover operators + DECP, resolve, report
# --------------------------------------------------------------------------- #
def run_live(
    *,
    api_base: str = DEFAULT_API_BASE,
    limit: int = 20,
    max_resource_mb: int = DEFAULT_MAX_RESOURCE_MB,
    snapshot_root: Path | None = None,
    out_dir: Path = OUT_DIR,
    operator_limit: int | None = None,
) -> dict[str, Any]:
    """Live end-to-end: discover operators + DECP, resolve each operator name to a SIREN, report."""
    print("=== Phase-0.5 spike — LIVE operator name->SIREN resolution (registry-driven) ===\n")
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
        base_url = recherche_base_url(get_source("recherche_entreprises"))
        denom_col = detect_column(operators["headers"], DENOM_PATTERNS)
        fallback_col = detect_column(operators["headers"], FALLBACK_PATTERNS)
        tutelle_col = detect_column(operators["headers"], TUTELLE_PATTERNS)
        name_cols = [c for c in (denom_col, fallback_col) if c]
        if not name_cols:
            raise SpikeAbort(
                f"Could not detect an operator-name column in {operators['headers']!r}."
            )
        print(
            f"\n[resolve] name columns (coalesced): {name_cols!r}  tutelle column: {tutelle_col!r}"
        )
        rows = operators["rows"][:operator_limit] if operator_limit else operators["rows"]
        print(f"[resolve] resolving {len(rows)} operator rows via {base_url} (~7 req/s)...")
        records = resolve_operators(
            client, rows, base_url, name_cols=name_cols, tutelle_col=tutelle_col
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

    resolved = {r["chosen_siren"] for r in records if r["chosen_siren"]}
    appearance = decp_appearance(resolved, decp["rows"], decp["headers"])
    decp_sirens = collect_sirens(decp["rows"], appearance["buyer_columns"]) | collect_sirens(
        decp["rows"], appearance["supplier_columns"]
    )
    csv_path = write_crosswalk_csv(records, decp_sirens, out_dir)

    summary = _summarize(
        records,
        appearance,
        mode="live",
        api_base=api_base,
        resolver_base_url=base_url,
        denomination_column=denom_col,
        denomination_fallback_column=fallback_col,
        tutelle_column=tutelle_col,
        operators_dataset=operators["dataset"],
        operators_snapshot=operators["snapshot_path"],
        decp_dataset=decp["dataset"],
        decp_snapshot=decp["snapshot_path"],
        decp_sampled_head=decp["sampled_head"],
        decp_distinct_sirens=len(decp_sirens),
        crosswalk_csv=str(csv_path),
        caveats=[
            "Resolution uses exact normalized-name equality only — never fuzzy auto-accept "
            "(golden rule #5). Ambiguous/unmatched operators are the FSC-23 backlog.",
            "The operator name is coalesce(leaf 'Opérateur de la catégorie', grouping 'Opérateur "
            "ou catégorie d'opérateurs'); a handful of pure category labels (e.g. 'Universités et "
            "assimilés') have no own SIREN and land in the backlog by design.",
            "tutelle is used only as a soft public-sector tie-breaker; a tutelle-code->entity map "
            "is deferred to FSC-23.",
            "DECP appearance is measured against a bounded HEAD SAMPLE of the ~2 GB consolidated "
            "CSV, not all of DECP — a presence signal, not a population estimate.",
        ],
    )
    _print_report(summary, appearance)
    print(f"\nCrosswalk artifact -> {csv_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "phase0_5_resolution_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Machine summary    -> {summary_path}")
    return summary


# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase-0.5 spike: operator name->SIREN resolution."
    )
    parser.add_argument("--sample", action="store_true", help="offline mode using fixtures")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="data.gouv.fr API base")
    parser.add_argument("--limit", type=int, default=20, help="datasets to fetch (live mode)")
    parser.add_argument(
        "--max-resource-mb", type=int, default=DEFAULT_MAX_RESOURCE_MB, help="cap a downloaded CSV"
    )
    parser.add_argument(
        "--operator-limit",
        type=int,
        default=None,
        help="cap operators resolved (live, for a quick run)",
    )
    args = parser.parse_args()

    if args.sample:
        summary = run_sample()
    else:
        try:
            summary = run_live(
                api_base=args.api_base,
                limit=args.limit,
                max_resource_mb=args.max_resource_mb,
                operator_limit=args.operator_limit,
            )
        except SpikeAbort as exc:
            print(f"[!] {exc}")
            sys.exit(exc.exit_code)
    sys.exit(0 if summary["exit_ok"] else 1)


if __name__ == "__main__":
    main()
