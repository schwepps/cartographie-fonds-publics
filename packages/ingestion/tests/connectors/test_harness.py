"""Offline self-test for the connector contract-test harness.

These tests exercise the harness itself — the ``load_fixture`` loader and the
respx-backed HTTP replay — so the "contract test against a fixture, no network"
pattern is proven to run fully offline in CI. Real connector contract tests follow
the same shape; see ``README.md`` in this directory for the template.
"""

import httpx
import pytest

# Connectors resolve resources via the data.gouv.fr catalog (never a frozen slug).
DATASETS_URL = "https://www.data.gouv.fr/api/1/datasets/"


def test_load_fixture_reads_bytes(load_fixture) -> None:
    raw = load_fixture("operateurs_sample.csv")
    assert raw.startswith(b"operateur,categorie,tutelle,siren")


def test_load_fixture_missing_raises(load_fixture) -> None:
    with pytest.raises(FileNotFoundError):
        load_fixture("__does_not_exist__.json")


def test_respx_replays_recorded_response_offline(load_fixture, respx_mock) -> None:
    """A recorded payload is replayed for a mocked URL — no real request leaves."""
    payload = load_fixture("datagouv_dataset_search.json")
    route = respx_mock.get(DATASETS_URL).mock(
        return_value=httpx.Response(200, content=payload),
    )

    with httpx.Client() as client:
        resp = client.get(DATASETS_URL, params={"q": "jaune opérateurs de l'État"})

    assert route.called
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["data"][0]["slug"] == "plf-2025-jaune-operateurs-de-letat"


def test_unmocked_request_is_blocked(respx_mock) -> None:
    """The offline guarantee: any request without a matching route raises, never
    falling through to the network."""
    respx_mock.get(DATASETS_URL).mock(return_value=httpx.Response(200))

    with httpx.Client() as client, pytest.raises(AssertionError):
        client.get("https://example.org/not-registered")
