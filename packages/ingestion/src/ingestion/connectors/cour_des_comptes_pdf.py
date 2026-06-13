"""Direct PDF fetch for Cour des comptes reports (FSC-67) — NOT a snapshot path.

The ``datagouv_api`` connector deliberately refuses to snapshot non-tabular formats:
``write_snapshot`` tabularises csv/json only, so a PDF raises ``SnapshotError`` (a dedicated
non-tabular snapshot path is FSC-38). The full-text extractor therefore downloads the report PDF
directly here, bounded and fail-loud, and never touches the snapshot layer. The bytes flow straight
into ``transforms.cour_des_comptes_extract.extract_text``.
"""

from __future__ import annotations

import httpx

HTTP_TIMEOUT = 30.0
MAX_PDF_BYTES = 50_000_000  # bound a download; a 404 HTML page or a runaway body fails loud
USER_AGENT = "cartographie-fonds-publics/ingestion (+https://cartographie-fonds-publics.fr)"
_PDF_MAGIC = b"%PDF-"


def fetch_pdf(url: str, *, max_bytes: int = MAX_PDF_BYTES) -> bytes:
    """Download a report PDF (bounded). Fail loud on oversize or a non-PDF body (e.g. a 404)."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError(f"refusing to fetch a non-http(s) URL: {url!r}")
    chunks: list[bytes] = []
    total = 0
    with (
        httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client,
        client.stream("GET", url, follow_redirects=True) as resp,
    ):
        resp.raise_for_status()
        for chunk in resp.iter_bytes():
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"PDF at {url} exceeded the {max_bytes}-byte cap")
    data = b"".join(chunks)
    if not data.startswith(_PDF_MAGIC):
        # A 200 that is actually an HTML error/redirect page must never be parsed as a PDF.
        raise ValueError(f"response from {url} is not a PDF (no %PDF- magic) — refusing to parse")
    return data
