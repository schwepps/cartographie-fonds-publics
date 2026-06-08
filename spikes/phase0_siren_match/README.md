# Phase-0 spike — SIREN match + registry-driven discovery

Proves the two riskiest assumptions before any real build:

1. We can **discover** the latest "jaune opérateurs" dataset via the data.gouv.fr `/api/1`
   catalog with **no hardcoded slug** (registry-driven).
2. **SIREN works as a join key** between State operators and public buyers in the
   procurement data (DECP). The headline metric is the **SIREN match rate** — the go/no-go
   signal for the institutional graph.

## Run

```bash
# Offline — always works, no network (default for `make spike`):
python spike.py --sample

# Live — discovery against data.gouv.fr (needs internet):
python spike.py
```

Only dependency: `pip install -r requirements.txt` (PyYAML).

## What success looks like

`--sample` prints a SIREN match rate and writes a tiny real graph
(`out/phase0_graph.json`: operator → contract → private supplier, keyed on SIREN). Exit code
is `0` when the match rate ≥ 50 %. The fixtures are illustrative; the live data will set the
true rate — improving SIREN coverage on the operators list is the first Phase-1 task if it's low.

## Files

- `spike.py` — the spike (stdlib + PyYAML).
- `fixtures/operateurs_sample.csv` — sample State operators (one intentionally without a SIREN).
- `fixtures/decp_sample.csv` — sample public contracts (buyers + suppliers).
- `out/` — generated graph (gitignored).
