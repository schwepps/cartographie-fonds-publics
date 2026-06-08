#!/usr/bin/env python3
"""Phase-0 spike — prove the data join before building.

It validates the two riskiest assumptions of the whole project:

1. **Registry-driven discovery** works: we can find the latest "jaune opérateurs"
   dataset via the data.gouv.fr /api/1 catalog *without any hardcoded slug*.
2. **SIREN is a usable join key**: State operators can be matched to public buyers
   in the procurement data (DECP). The headline output is the **SIREN match rate** —
   the #1 go/no-go indicator for the institutional graph.

Modes
-----
    python spike.py --sample      # offline, uses bundled fixtures (default for `make spike`)
    python spike.py               # live: discover the latest dataset via data.gouv.fr

Only dependency: PyYAML (see requirements.txt). Networking uses the stdlib.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
REGISTRY_PATH = REPO_ROOT / "data" / "registry" / "sources-registry.yaml"
FIXTURES = HERE / "fixtures"
OUT_DIR = HERE / "out"

DEFAULT_API_BASE = "https://www.data.gouv.fr/api/1"


# --------------------------------------------------------------------------- #
# Shared helpers
# NOTE: `normalize_siren`, `load_registry` and `get_source` below are deliberately
# re-implemented here so this Phase-0 spike stays stdlib-only (PyYAML aside) and
# independent of the workspace packages. They duplicate `core.resolve` /
# `ingestion.registry` on purpose — delete this spike once Phase 1 connectors exist.
# --------------------------------------------------------------------------- #
def normalize_siren(value: str | None) -> str | None:
    """Return a 9-digit SIREN or None. Never guess."""
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 9 else None


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_source(registry: dict, source_id: str) -> dict:
    for source in registry.get("sources", []):
        if source["id"] == source_id:
            return source
    raise KeyError(f"Unknown source id: {source_id!r}")


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
    match_rate = len(matched) / resolvable if resolvable else 0.0

    print(f"Operators (rows)............... {total_ops}")
    print(f"  with a usable SIREN.......... {resolvable}  ({coverage:.0%} coverage)")
    print(f"  matched to a DECP buyer...... {len(matched)}")
    print(f"\n>>> SIREN MATCH RATE (resolvable): {match_rate:.0%}")
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

    verdict = "VIABLE" if match_rate >= 0.5 else "NEEDS-WORK (improve SIREN coverage)"
    print("\nInterpretation: a real graph edge was built from public money to a private")
    print(f"supplier, keyed on SIREN. Graph viability on this sample: {verdict}.")
    return match_rate


# --------------------------------------------------------------------------- #
# Live mode: registry-driven discovery (no hardcoded slug)
# --------------------------------------------------------------------------- #
def _http_get_json(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "cfp-phase0-spike"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (public API)
        return json.loads(resp.read().decode("utf-8"))


def _latest_by_year(datasets: list[dict]) -> dict | None:
    """Pick the dataset whose title carries the most recent 4-digit year."""
    best, best_year = None, -1
    for d in datasets:
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", d.get("title", ""))]
        year = max(years) if years else 0
        if year > best_year:
            best, best_year = d, year
    return best


def run_live(api_base: str, limit: int) -> None:
    print("=== Phase-0 spike — LIVE discovery (registry-driven) ===\n")
    registry = load_registry()
    source = get_source(registry, "operateurs_etat")
    query = "jaune opérateurs de l'État"  # from the registry discovery strategy, not a slug

    print(f"Source id .......... {source['id']}")
    print(f"Discovery strategy . {source['discovery'].get('strategy')}")
    print(f"Query .............. {query!r}\n")

    url = f"{api_base}/datasets/?{urllib.parse.urlencode({'q': query, 'page_size': limit})}"
    try:
        payload = _http_get_json(url)
    except Exception as exc:  # noqa: BLE001
        print(f"[!] Network call failed ({exc}).")
        print("    Run the offline proof instead:  python spike.py --sample")
        sys.exit(2)

    datasets = payload.get("data", [])
    if not datasets:
        print("[!] No datasets returned. Try a broader query or run --sample.")
        sys.exit(2)

    latest = _latest_by_year(datasets) or datasets[0]
    print("Resolved latest millésime WITHOUT a hardcoded slug:")
    print(f"  title: {latest.get('title')}")
    print(f"  id   : {latest.get('id')}")
    print(f"  page : {latest.get('page')}\n")

    resources = (latest.get("resources") or [])[:5]
    print(f"First resources ({len(resources)} shown):")
    for r in resources:
        print(f"  - [{r.get('format')}] {r.get('title')}  {r.get('url')}")

    print("\nNext (Phase 1): download the CSV, validate against its Table Schema,")
    print("snapshot it, then compute the SIREN match rate as in --sample mode.")


# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="Phase-0 spike: SIREN join + discovery.")
    parser.add_argument("--sample", action="store_true", help="offline mode using fixtures")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="data.gouv.fr API base")
    parser.add_argument("--limit", type=int, default=20, help="datasets to fetch (live mode)")
    args = parser.parse_args()

    if args.sample:
        rate = run_sample()
        sys.exit(0 if rate >= 0.5 else 1)
    run_live(args.api_base, args.limit)


if __name__ == "__main__":
    main()
