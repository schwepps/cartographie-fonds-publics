# Phase-0 spike — SIREN match + registry-driven discovery

Proves the two riskiest assumptions before any real build:

1. We can **discover** the latest "jaune opérateurs" and DECP datasets via the data.gouv.fr
   `/api/1` catalog with **no hardcoded slug** (registry-driven).
2. **SIREN works as a join key** between State operators and public buyers/suppliers in the
   procurement data (DECP). The headline metrics are operator **SIREN coverage** and the
   **SIREN match rate** — the go/no-go signal for the institutional graph.

## Run

```bash
# Offline — always works, no network (default for `make spike`):
make spike            # python spike.py --sample

# Live, end-to-end — discover, download, validate, snapshot, then MATCH (needs internet):
make spike-live       # python spike.py
```

Offline mode needs only PyYAML + the stdlib. **Live mode reuses the workspace packages**
(`core.resolve`, `ingestion.validation`, `ingestion.snapshot`) and so runs through the uv
workspace venv — use `make spike-live`, not a bare `python`.

## What success looks like

`--sample` prints a SIREN match rate and writes a tiny real graph
(`out/phase0_graph.json`: operator → contract → private supplier, keyed on SIREN); exit `0` when
the rate ≥ 50 %. Live mode discovers both datasets, snapshots the raw extracts to
`data/snapshots/`, computes operator coverage + the match rate against a bounded DECP head sample,
and writes a machine summary to `out/phase0_live_summary.json`. The recorded go/no-go lives in
[`docs/phase0-siren-match-results.md`](../../docs/phase0-siren-match-results.md).

## Files

- `spike.py` — the spike (offline `--sample` + live pipeline).
- `fixtures/` — sample operators + contracts for offline mode.
- `tests/` — offline respx tests (mock the catalog + downloads; no network).
- `out/` — generated graph + live summary (gitignored).
