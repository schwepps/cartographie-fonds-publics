"""Direct PDF fetch for Cour des comptes reports (FSC-67) — NOT a snapshot path.

The ``datagouv_api`` connector deliberately refuses to snapshot non-tabular formats:
``write_snapshot`` tabularises csv/json only, so a PDF raises ``SnapshotError`` (a dedicated
non-tabular snapshot path is FSC-38). The full-text extractor therefore downloads the report PDF
directly here, bounded and fail-loud, and never touches the snapshot layer. It lives outside
``connectors/`` on purpose: it is a plain helper, not a registered ``Connector``. The bytes flow
straight into ``transforms.cour_des_comptes_extract.extract_text``.

SSRF guard: the scheme is re-validated and obvious internal/literal-IP targets are rejected on the
initial URL **and on every redirect hop** (httpx is driven with ``follow_redirects=False`` and the
hops are followed manually) — a 3xx to ``file://`` or a metadata IP can't slip past the check.
A hostname that *resolves* to a private IP is not caught here (that needs a DNS lookup, which would
break the offline contract tests) — full egress control belongs to the CI network policy.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx

HTTP_TIMEOUT = 30.0
MAX_PDF_BYTES = 50_000_000  # bound a download; a 404 HTML page or a runaway body fails loud
MAX_REDIRECTS = 5
USER_AGENT = "cartographie-fonds-publics/ingestion (+https://cartographie-fonds-publics.fr)"
_PDF_MAGIC = b"%PDF-"
_BLOCKED_HOSTS = frozenset({"localhost", "metadata", "metadata.google.internal"})


def _validate_target(url: str) -> None:
    """Reject non-http(s) URLs and obvious internal/literal-IP targets (SSRF guard, no DNS)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"refusing to fetch a non-http(s) URL: {url!r}")
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS:
        raise ValueError(f"refusing to fetch an internal/empty host: {url!r}")
    try:
        ip = ipaddress.ip_address(host)  # only when the host is a literal IP
    except ValueError:
        ip = None
    if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
        raise ValueError(f"refusing to fetch a private/internal IP: {url!r}")


def fetch_pdf(url: str, *, max_bytes: int = MAX_PDF_BYTES) -> bytes:
    """Download a report PDF (bounded, redirect-validated); fail loud on oversize or a non-PDF."""
    _validate_target(url)
    data = b""
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            with client.stream("GET", current, follow_redirects=False) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise ValueError(f"redirect from {current} carried no Location header")
                    current = str(httpx.URL(current).join(location))
                    _validate_target(current)  # re-check scheme/host on every hop
                    continue
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"PDF at {current} exceeded the {max_bytes}-byte cap")
                data = b"".join(chunks)
                break
        else:
            raise ValueError(f"too many redirects (> {MAX_REDIRECTS}) fetching {url}")
    if not data.startswith(_PDF_MAGIC):
        # A 200 that is actually an HTML error/redirect page must never be parsed as a PDF.
        raise ValueError(f"response from {url} is not a PDF (no %PDF- magic) — refusing to parse")
    return data
