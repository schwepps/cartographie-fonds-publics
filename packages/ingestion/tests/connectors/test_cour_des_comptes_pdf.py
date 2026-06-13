"""Offline contract test for the direct Cour des comptes PDF fetch (FSC-67).

respx blocks the network: the download runs against a recorded fixture. Proves the bytes come back,
that an unmocked URL raises (the offline guarantee), and that a non-PDF body (e.g. a 404 HTML page)
fails loud rather than being parsed as a PDF.
"""

from __future__ import annotations

import httpx
import pytest
from ingestion.connectors.cour_des_comptes_pdf import fetch_pdf

URL = "https://www.ccomptes.fr/fr/publications/exemple.pdf"


def test_fetch_pdf_returns_bytes(load_fixture, respx_mock) -> None:  # type: ignore[no-untyped-def]
    pdf = load_fixture("ccomptes_sample.pdf")
    respx_mock.get(URL).mock(return_value=httpx.Response(200, content=pdf))
    assert fetch_pdf(URL).startswith(b"%PDF-")


def test_fetch_pdf_unmocked_url_raises(respx_mock) -> None:  # type: ignore[no-untyped-def]
    # respx raises on any unmocked request — the offline guarantee.
    with pytest.raises(Exception):  # noqa: B017 — respx surfaces its own connect error type
        fetch_pdf(URL)


def test_fetch_pdf_rejects_non_pdf_body(respx_mock) -> None:  # type: ignore[no-untyped-def]
    respx_mock.get(URL).mock(
        return_value=httpx.Response(200, content=b"<html>404 not found</html>")
    )
    with pytest.raises(ValueError, match="not a PDF"):
        fetch_pdf(URL)


def test_fetch_pdf_rejects_non_http_url() -> None:
    with pytest.raises(ValueError, match="non-http"):
        fetch_pdf("file:///etc/passwd")
