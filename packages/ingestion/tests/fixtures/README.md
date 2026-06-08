# Connector test fixtures

Recorded HTTP payloads and sample extracts used by **offline** connector contract
tests. Nothing here is fetched at test time — connectors hit the network only in
production, never in the test suite (see [`../connectors/README.md`](../connectors/README.md)).

## What belongs here

- **Recorded API responses** — trimmed catalog/discovery payloads (e.g. a data.gouv.fr
  `/api/1/datasets/` search result) that a connector's `discover()` step parses.
- **Sample extracts** — tiny CSV/JSON resources standing in for what `extract()`
  downloads, used to exercise `validate()`/`stage()` parsing.

Load them in tests via the `load_fixture` pytest fixture (see `../conftest.py`).

## Rules

- **Small samples only.** Header + 2–3 rows for tabular data; a couple of records for
  API envelopes. Just enough to exercise parsing — never a full dump.
- **No secrets, no PII, no raw snapshots.** Use public, illustrative values. IDs and
  SIRENs here are representative, not authoritative.
- **Keep the real shape.** Trim the *size*, not the *structure* — preserve the envelope
  keys (`data`, `next_page`, `total`, …) and field names the connector relies on, so the
  fixture stays a faithful contract.

## Naming convention

`<platform>_<purpose>.<ext>` — lowercase, snake_case. Examples:

| File | Purpose |
| -- | -- |
| `datagouv_dataset_search.json` | data.gouv.fr `/api/1/datasets/` search envelope (discovery) |
| `operateurs_sample.csv` | Sample extracted "Jaune opérateurs" resource |

## Recording a new fixture

1. Hit the real endpoint once, manually (e.g. `curl '<url>' | jq` or a one-off script).
2. **Trim** it to the smallest payload that still reproduces the parsing path.
3. Scrub anything sensitive; keep the structure intact.
4. Save it here under the naming convention and wire it into a test with `respx_mock`.
