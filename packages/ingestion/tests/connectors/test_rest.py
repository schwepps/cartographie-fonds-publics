"""Offline contract test for the PISTE/Légifrance ``rest`` connector (FSC-66).

respx blocks the network: the OAuth2 token mint, the LODA search and the per-text consult all run
against recorded fixtures. Proves credential reading, that discovery reads text ids from the API
payload (never a frozen id, golden rule #2), that extract consults each text, that an empty result
set and missing credentials both fail loud, and that the JSON extract snapshots with provenance.
"""

from __future__ import annotations

import json
from functools import partial

import httpx
import ingestion.connectors.rest as mod
import pytest
from ingestion.connectors import get_connector
from ingestion.connectors.rest import (
    LEGIFRANCE_API_BASE,
    LODA_CONSULT_PATH,
    LODA_SEARCH_PATH,
    PISTE_CLIENT_ID_ENV,
    PISTE_CLIENT_SECRET_ENV,
    PISTE_TOKEN_URL,
    RestConnector,
)
from ingestion.registry import get_source

SEARCH_URL = f"{LEGIFRANCE_API_BASE}{LODA_SEARCH_PATH}"
CONSULT_URL = f"{LEGIFRANCE_API_BASE}{LODA_CONSULT_PATH}"

_SOURCE = {
    "id": "legifrance_attributions",
    "license": "Licence Ouverte 2.0",
    "discovery": {"strategy": "Recherche par texte (décret d'attribution)"},
}


@pytest.fixture
def _creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PISTE_CLIENT_ID_ENV, "id")
    monkeypatch.setenv(PISTE_CLIENT_SECRET_ENV, "secret")


def test_registry_routes_rest_platform_to_rest_connector() -> None:
    # The real registry source `legifrance_attributions` is `platform: rest`; the factory must
    # resolve it to RestConnector (before this connector existed, get_connector raised).
    connector = get_connector(get_source("legifrance_attributions"))
    assert isinstance(connector, RestConnector)


def test_reads_piste_credentials_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PISTE_CLIENT_ID_ENV, raising=False)
    monkeypatch.delenv(PISTE_CLIENT_SECRET_ENV, raising=False)
    assert RestConnector().has_credentials is False
    monkeypatch.setenv(PISTE_CLIENT_ID_ENV, "id")
    monkeypatch.setenv(PISTE_CLIENT_SECRET_ENV, "secret")
    assert RestConnector().has_credentials is True


def test_empty_env_placeholders_count_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    # The .env.example ships empty placeholders; those must not read as "configured".
    monkeypatch.setenv(PISTE_CLIENT_ID_ENV, "")
    monkeypatch.setenv(PISTE_CLIENT_SECRET_ENV, "")
    assert RestConnector().has_credentials is False


def test_discover_mints_token_and_resolves_loda_texts(load_fixture, _creds, respx_mock) -> None:  # type: ignore[no-untyped-def]
    token_route = respx_mock.post(PISTE_TOKEN_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("piste_token.json"))
    )
    search_route = respx_mock.post(SEARCH_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("piste_loda_search.json"))
    )
    resolved = RestConnector().discover(_SOURCE)

    assert token_route.called and search_route.called
    # The search is authenticated with the minted bearer token.
    assert search_route.calls.last.request.headers["Authorization"] == "Bearer test-piste-token"
    # Text ids come from the payload, never hardcoded (golden rule #2).
    cids = [t["cid"] for t in resolved["texts"]]
    assert cids == ["JORFTEXT000052457068", "JORFTEXT000052457900"]
    # JORF text ids resolve under /jorf/id/ (not /loda/id/) — matches the committed example backlog.
    assert (
        resolved["texts"][0]["url"] == "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052457068"
    )
    assert resolved["license"] == "Licence Ouverte 2.0"


def test_discover_without_credentials_fails_loud(
    monkeypatch: pytest.MonkeyPatch, respx_mock
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv(PISTE_CLIENT_ID_ENV, raising=False)
    monkeypatch.delenv(PISTE_CLIENT_SECRET_ENV, raising=False)
    with pytest.raises(RuntimeError, match="PISTE"):
        RestConnector().discover(_SOURCE)  # raises before any HTTP — respx records no call


def test_extract_consults_each_text(load_fixture, _creds, respx_mock) -> None:  # type: ignore[no-untyped-def]
    respx_mock.post(PISTE_TOKEN_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("piste_token.json"))
    )
    consult_route = respx_mock.post(CONSULT_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("piste_consult_decree.json"))
    )
    resolved = {
        "texts": [
            {
                "id": "JORFTEXT000052457068",
                "cid": "JORFTEXT000052457068",
                "title": "Décret ... attributions du ministre de la culture",
                "date": "2025-10-30",
                "url": "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000052457068",
            }
        ]
    }
    raw = RestConnector().extract(resolved)

    assert consult_route.called
    payload = json.loads(raw)
    assert payload["texts"][0]["cid"] == "JORFTEXT000052457068"
    # The HTML article body is flattened to plain text for the linker.
    assert "ministre de la culture conduit" in payload["texts"][0]["content"]


def test_extract_empty_texts_fails_loud() -> None:
    with pytest.raises(ValueError, match="no LODA texts"):
        RestConnector().extract({"texts": []})


def test_search_retries_on_429_then_succeeds(  # type: ignore[no-untyped-def]
    load_fixture, _creds, respx_mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    # PISTE's free tier rate-limits; a 429 must be retried (Retry-After), not abort the run.
    monkeypatch.setattr(mod, "_pause", lambda *_: None)  # no real backoff in the test
    respx_mock.post(PISTE_TOKEN_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("piste_token.json"))
    )
    search = respx_mock.post(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200, content=load_fixture("piste_loda_search.json")),
        ]
    )
    resolved = RestConnector().discover(_SOURCE)
    assert search.call_count == 2  # retried once after the 429
    assert [t["cid"] for t in resolved["texts"]] == [
        "JORFTEXT000052457068",
        "JORFTEXT000052457900",
    ]


def test_consult_retries_on_read_timeout(  # type: ignore[no-untyped-def]
    load_fixture, _creds, respx_mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A slow consult (read timeout) is transient on the free tier — retry, don't drop the décret.
    monkeypatch.setattr(mod, "_pause", lambda *_: None)
    respx_mock.post(PISTE_TOKEN_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("piste_token.json"))
    )
    consult = respx_mock.post(CONSULT_URL).mock(
        side_effect=[
            httpx.ReadTimeout("slow consult"),
            httpx.Response(200, content=load_fixture("piste_consult_decree.json")),
        ]
    )
    resolved = {
        "texts": [
            {
                "id": "X",
                "cid": "X",
                "title": "Décret ...",
                "date": "2025-10-30",
                "url": "https://www.legifrance.gouv.fr/loda/id/X",
            }
        ]
    }
    raw = RestConnector().extract(resolved)
    assert consult.call_count == 2  # retried once after the timeout
    assert json.loads(raw)["texts"][0]["cid"] == "X"


def test_search_429_exhausts_retries_then_fails_loud(  # type: ignore[no-untyped-def]
    load_fixture, _creds, respx_mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    # If the rate limit never clears, fail loud (never silently emit an empty/partial extract).
    monkeypatch.setattr(mod, "_pause", lambda *_: None)
    respx_mock.post(PISTE_TOKEN_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("piste_token.json"))
    )
    respx_mock.post(SEARCH_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(httpx.HTTPStatusError):
        RestConnector().discover(_SOURCE)


def test_long_retry_after_fails_fast_without_retrying(  # type: ignore[no-untyped-def]
    load_fixture, _creds, respx_mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The free-tier daily quota returns a multi-hour Retry-After; don't burn retries — fail loud
    # immediately with the reset time so the operator reruns later.
    monkeypatch.setattr(mod, "_pause", lambda *_: None)
    respx_mock.post(PISTE_TOKEN_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("piste_token.json"))
    )
    search = respx_mock.post(SEARCH_URL).mock(
        return_value=httpx.Response(429, headers={"Retry-After": "26195"})
    )
    with pytest.raises(RuntimeError, match="quota exhausted"):
        RestConnector().discover(_SOURCE)
    assert search.call_count == 1  # no pointless retries


def test_retry_after_zero_is_honored_not_treated_as_falsy(  # type: ignore[no-untyped-def]
    load_fixture, _creds, respx_mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Retry-After: 0 means "retry immediately"; 0 is a valid value, not falsy — it must NOT fall
    # back to exponential backoff.
    waits: list[float] = []
    monkeypatch.setattr(mod, "_pause", waits.append)
    respx_mock.post(PISTE_TOKEN_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("piste_token.json"))
    )
    respx_mock.post(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, content=load_fixture("piste_loda_search.json")),
        ]
    )
    RestConnector().discover(_SOURCE)
    assert waits == [0.0]  # honored the 0, did not back off


def test_snapshot_writes_provenance_parquet(_creds, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Redirect the snapshot root (import-time bound) so the test never writes to data/.
    monkeypatch.setattr(mod, "write_snapshot", partial(mod.write_snapshot, root=tmp_path))
    connector = RestConnector()
    raw = (
        b'{"texts": [{"id": "X", "cid": "X", "title": "t", "date": "2025-10-30", '
        b'"url": "https://legifrance/loda/id/X", "content": "Le ministre ..."}]}'
    )
    path = connector.snapshot(raw, "legifrance_attributions")
    assert path.endswith(".parquet")
    assert (tmp_path / "legifrance_attributions" / "latest.json").is_file()


def test_stage_defers_to_cross_source_loader() -> None:
    with pytest.raises(NotImplementedError, match="FSC-35"):
        RestConnector().stage("snap://x", "legifrance_attributions")
