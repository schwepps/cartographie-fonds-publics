"""Offline contract test for the direct Cour des comptes PDF fetch (FSC-67).

respx blocks the network: the download runs against a recorded fixture. Proves the bytes come back,
that an unmocked URL raises (the offline guarantee), that a non-PDF body fails loud, and that the
SSRF guard rejects non-http(s) URLs, internal hosts, and redirect hops to unsafe targets.
"""

from __future__ import annotations

import httpx
import pytest
from ingestion.report_fetch import fetch_pdf

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


def test_fetch_pdf_rejects_internal_literal_ip() -> None:
    # The cloud-metadata IP and loopback must be refused before any request (SSRF).
    with pytest.raises(ValueError, match="private/internal IP"):
        fetch_pdf("http://169.254.169.254/latest/meta-data/")


def test_fetch_pdf_revalidates_redirect_target(load_fixture, respx_mock) -> None:  # type: ignore[no-untyped-def]
    # A 3xx to a file:// (or internal) target must be caught on the hop, not followed.
    respx_mock.get(URL).mock(
        return_value=httpx.Response(302, headers={"location": "file:///etc/passwd"})
    )
    with pytest.raises(ValueError, match="non-http"):
        fetch_pdf(URL)


def test_fetch_pdf_follows_safe_redirect(load_fixture, respx_mock) -> None:  # type: ignore[no-untyped-def]
    # A redirect to another https target IS followed (manual redirect handling still works).
    final = "https://www.ccomptes.fr/sites/default/files/exemple.pdf"
    respx_mock.get(URL).mock(return_value=httpx.Response(301, headers={"location": final}))
    respx_mock.get(final).mock(
        return_value=httpx.Response(200, content=load_fixture("ccomptes_sample.pdf"))
    )
    assert fetch_pdf(URL).startswith(b"%PDF-")
