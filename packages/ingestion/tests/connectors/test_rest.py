"""Offline contract test for the PISTE/Légifrance ``rest`` connector (FSC-27, manual-first).

No HTTP: Phase-1 attributions are editorial, so the connector registers the ``rest`` platform and
reads the PISTE OAuth2 credentials, but ``discover``/``extract`` defer to the editorial transform
with an actionable message (live extraction is FSC-66). This pins registration, credential reading,
and the deferral contract — fully offline, no network.
"""

from __future__ import annotations

import pytest
from ingestion.connectors import get_connector
from ingestion.connectors.rest import (
    PISTE_CLIENT_ID_ENV,
    PISTE_CLIENT_SECRET_ENV,
    RestConnector,
)
from ingestion.registry import get_source


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


def test_discover_defers_with_actionable_message() -> None:
    with pytest.raises(NotImplementedError, match="FSC-66"):
        RestConnector().discover(
            {"id": "legifrance_attributions", "license": "Licence Ouverte 2.0"}
        )


def test_extract_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        RestConnector().extract({})


def test_stage_defers_to_cross_source_loader() -> None:
    with pytest.raises(NotImplementedError, match="FSC-35"):
        RestConnector().stage("snap://x", "legifrance_attributions")
