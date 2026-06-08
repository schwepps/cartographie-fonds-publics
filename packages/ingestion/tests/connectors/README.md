# Connector contract-test template

Every connector ships a **contract test against a fixture, with no network** — that is a
[Definition of Done](../../../../CLAUDE.md) requirement. This directory holds those tests
and the harness that makes them offline-by-construction.

## The harness

Two pieces, both already wired up — you don't set anything up:

| Tool | Where | Gives you |
| -- | -- | -- |
| `load_fixture` | [`../conftest.py`](../conftest.py) | `load_fixture("name.ext") -> bytes`, reading from [`../fixtures/`](../fixtures/) |
| `respx_mock` | respx pytest plugin | Mocks the httpx transport; **any unmocked request raises** (see `test_harness.py::test_unmocked_request_is_blocked`) |

Because respx blocks unmatched requests, a connector test physically *cannot* reach the
network — that is the offline guarantee, enforced rather than trusted.

## The pattern

1. **Record** a payload from the real endpoint, trim it, and drop it in
   [`../fixtures/`](../fixtures/) (see that directory's README for the rules).
2. **Wire** the recorded payload to its URL with `respx_mock`.
3. **Drive** the connector method (`discover` / `extract` / `validate` / …).
4. **Assert** on the parsed result. No network, ever.

## Template

Copy this when adding a connector test. It targets a hypothetical `DatagouvConnector`
implementing the [`Connector` ABC](../../src/ingestion/connectors/base.py); swap in the
real class and fixtures once the connector exists.

The connector self-registers with `@register("<platform>")` keyed on its registry
`platform` (`datagouv_api`, `ods_explore`, `rest`). That single decorator is all the
dispatch wiring there is — `get_connector(source)` finds it automatically, with no edits
to `cli.py` or `connectors/__init__.py`:

```python
from ingestion.connectors import Connector, register


@register("datagouv_api")
class DatagouvConnector(Connector):
    ...  # implement discover/extract/validate/snapshot/stage
```

A connector module must do nothing at import time except register — no network, no
`get_connector` calls, no other side effects. Auto-discovery imports every sibling module,
so a module that fails or does work on import fails the whole pipeline (loudly, as a
`ConnectorImportError` naming the module).

```python
import httpx

from ingestion.connectors.datagouv import DatagouvConnector  # your connector

DATASETS_URL = "https://www.data.gouv.fr/api/1/datasets/"


def test_discover_resolves_latest_millesime(load_fixture, respx_mock) -> None:
    # 1+2. Wire the recorded catalog response to the discovery URL.
    payload = load_fixture("datagouv_dataset_search.json")
    respx_mock.get(DATASETS_URL).mock(
        return_value=httpx.Response(200, content=payload),
    )

    # 3. Drive the connector's discover() step against the registry source dict.
    source = {
        "discovery": {"strategy": "search_datasets(query='jaune opérateurs')"},
    }
    resolved = DatagouvConnector().discover(source)

    # 4. Assert it picked the most recent millésime — no frozen slug, no network.
    assert resolved["slug"] == "plf-2025-jaune-operateurs-de-letat"
    assert resolved["resource_url"].endswith("a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")


def test_validate_fails_loud_on_schema_drift(load_fixture) -> None:
    # extract() output can be replayed straight from a sample fixture — no HTTP needed.
    raw = load_fixture("operateurs_sample.csv")
    DatagouvConnector().validate(raw, schema_ref=None)  # raises on drift; see golden rules
```

### Notes

- **Match only what matters.** `respx_mock.get(URL)` matches method + host + path; extra
  query params on the request still match. Constrain further with `params=...` only when
  the test is specifically about them.
- **Reuse fixtures across steps.** The same `operateurs_sample.csv` that stands in for an
  `extract()` download also feeds `validate()`/`stage()` parse tests.
- **Keep it offline.** Never add a live fallback or a real URL the mock doesn't cover —
  `test_unmocked_request_is_blocked` documents why the suite refuses it.

See [`test_harness.py`](test_harness.py) for runnable, offline examples of every piece.
