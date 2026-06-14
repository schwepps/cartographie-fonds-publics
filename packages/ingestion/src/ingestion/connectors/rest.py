"""Connector for ``platform: rest`` sources — the PISTE/Légifrance API (FSC-27 → FSC-66).

The registry source ``legifrance_attributions`` is ``platform: rest`` with ``auth: clé API PISTE``.
This connector performs the live discovery loop: a PISTE OAuth2 *client-credentials* token mint, a
Légifrance **LODA** search for « décret d'attribution » (discovery by query — never a frozen text
id, golden rule #2), and a per-text *consult* to fetch the full text. ``extract`` returns the
décrets as JSON for the deterministic, editorial-assisted text→entity linker
(:mod:`ingestion.transforms.legifrance_candidates`), which routes each décret to a ministry SIREN
candidate or the human-review backlog — **never auto-published** (golden rule #5).

The PISTE credentials are read from the environment (server/CI only, never committed, never the
browser). ``discover``/``extract`` fail loud with an actionable message when they are absent, so the
live path is opt-in behind the operator-provisioned secret. ``validate``/``snapshot`` delegate to
the shared helpers; ``stage`` defers to the cross-source loader (FSC-35), like the other connectors.

The published « pourquoi » layer stays the reviewed editorial YAML
(``ingestion.transforms.legifrance_attributions`` → ``data/attributions/ministres.yaml``): this
connector + the candidate linker are the (semi-)automated *discovery* that feeds the review backlog,
not a replacement for human validation.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from ..snapshot import write_snapshot
from ..validation import validate_extract
from . import Connector, register

# PISTE uses OAuth2 client-credentials; both are required to mint a bearer token. Server/CI only,
# never the frontend (see .env.example). Read from the env, never hardcoded.
PISTE_CLIENT_ID_ENV = "PISTE_CLIENT_ID"
PISTE_CLIENT_SECRET_ENV = "PISTE_CLIENT_SECRET"

# PISTE / Légifrance API hosts (platform infrastructure, not a document id).
PISTE_TOKEN_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
PISTE_SCOPE = "openid"
LEGIFRANCE_API_BASE = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
LODA_SEARCH_PATH = "/search"
LODA_CONSULT_PATH = "/consult/lawDecree"
# Public Légifrance permalink bases (the human-citable source_url on each candidate). A JORF text id
# (JORFTEXT…) resolves under /jorf/id/; a consolidated LODA id (LEGITEXT…) under /loda/id/.
LEGIFRANCE_LODA_BASE = "https://www.legifrance.gouv.fr/loda/id"
LEGIFRANCE_JORF_BASE = "https://www.legifrance.gouv.fr/jorf/id"

DEFAULT_DECREE_QUERY = "décret d'attribution"
DEFAULT_LICENSE = "Licence Ouverte 2.0"
# Envelope key wrapping the décret records in the extract JSON — shared by extract() (writer) and
# snapshot() (record_path, so write_snapshot tabularises the array, not the wrapping object).
EXTRACT_ENVELOPE_KEY = "texts"
SEARCH_PAGE_SIZE = 50
HTTP_TIMEOUT = 60.0  # generous read timeout — PISTE/Légifrance consults can be slow (FSC-69)
USER_AGENT = "cartographie-fonds-publics/ingestion (+https://cartographie-fonds-publics.fr)"

# Live PISTE free-tier resilience (FSC-69): the API rate-limits (429) and is occasionally slow, so a
# multi-décret run must retry transient failures instead of aborting on the first one. Honor
# Retry-After on 429, back off (capped exponential) on 429-without-header and on read/connect
# timeouts, and pace consults to avoid bursting the quota. Tests patch `_pause` (no real wait).
PISTE_MAX_RETRIES = 4
PISTE_BACKOFF_BASE = 2.0
PISTE_BACKOFF_CAP = 30.0
PISTE_CONSULT_THROTTLE = 0.5

_MISSING_CREDS_MSG = (
    "Live PISTE/Légifrance extraction needs the OAuth2 credentials "
    f"{PISTE_CLIENT_ID_ENV}/{PISTE_CLIENT_SECRET_ENV} (a free PISTE account, provisioned by an "
    "operator — it cannot be minted from code). Set them in the environment (CI secret / .env, "
    "never committed) to run discover/extract. Phase-1 attributions render from the reviewed "
    "editorial YAML in the meantime (ingestion.transforms.legifrance_attributions)."
)

# A query phrase named in the registry discovery.strategy, e.g. "...(décret d'attribution)...".
_PAREN_RE = re.compile(r"\(([^)]+)\)")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _pause(seconds: float) -> None:
    """Sleep wrapper — patched to a no-op in offline tests so retry/throttle add no real delay."""
    if seconds > 0:
        time.sleep(seconds)


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    """Parse a ``Retry-After`` delta-seconds header to a float (uncapped), else None."""
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _request_with_retry(
    client: httpx.Client, method: str, url: str, **kwargs: Any
) -> httpx.Response:
    """Issue a request, retrying transient failures; fail loud on anything else.

    PISTE's free tier rate-limits (429) and is occasionally slow, so a single 429 or read timeout
    must not abort a multi-décret run. Retries on 429 (honoring ``Retry-After``) and on
    read/connect timeouts with capped exponential backoff; other HTTP errors still raise via
    ``raise_for_status``.
    """
    timeouts = (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout)
    for attempt in range(PISTE_MAX_RETRIES + 1):
        final = attempt == PISTE_MAX_RETRIES
        backoff = min(PISTE_BACKOFF_BASE * 2**attempt, PISTE_BACKOFF_CAP)
        try:
            resp = client.request(method, url, **kwargs)
        except timeouts:
            if final:
                raise
            _pause(backoff)
            continue
        if resp.status_code == 429 and not final:
            retry_after = _retry_after_seconds(resp)
            if retry_after is not None and retry_after > PISTE_BACKOFF_CAP:
                # The server asks us to wait far longer than we'll block mid-run (the PISTE
                # free-tier daily quota does this — a Retry-After of hours). Fail loud with the
                # reset time so the operator reruns later, not burning bounded retries for nothing.
                raise RuntimeError(
                    f"PISTE rate limit: Retry-After={int(retry_after)}s "
                    f"(~{retry_after / 3600:.1f}h) — free-tier quota exhausted; rerun after reset."
                )
            _pause(backoff if retry_after is None else retry_after)  # honor Retry-After: 0
            continue
        resp.raise_for_status()
        return resp
    raise AssertionError("unreachable")  # the loop returns or raises on the final attempt


@register("rest")
class RestConnector(Connector):
    """PISTE/Légifrance connector: OAuth2 token → LODA search → consult (FSC-66)."""

    def __init__(self) -> None:
        # Empty string env vars (the .env.example placeholders) count as absent.
        self._client_id = os.environ.get(PISTE_CLIENT_ID_ENV) or None
        self._client_secret = os.environ.get(PISTE_CLIENT_SECRET_ENV) or None
        self._source_id: str = "legifrance_attributions"
        self._license: str | None = None
        self._source_ref: str | None = None
        self._token: str | None = None

    @property
    def has_credentials(self) -> bool:
        """True iff both PISTE OAuth2 credentials are present (needed for the live FSC-66 path)."""
        return bool(self._client_id and self._client_secret)

    # -- discover ----------------------------------------------------------- #
    def discover(self, source: dict[str, Any]) -> dict[str, Any]:
        """Mint a PISTE token, run the LODA search for décrets d'attribution, return the hits.

        Discovery is by **query** (derived from the registry ``discovery.strategy`` or the default
        « décret d'attribution »), never a frozen text id — the ids come back from the API payload
        (golden rule #2). Provenance (source id, licence, search endpoint) is captured for snapshot.
        """
        self._source_id = str(source.get("id") or self._source_id)
        self._license = source.get("license") or DEFAULT_LICENSE
        query = _decree_query(source)
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
            token = self._mint_token(client)
            payload = self._loda_search(client, token, query)
        texts = _parse_search_results(payload)
        self._source_ref = f"{LEGIFRANCE_API_BASE}{LODA_SEARCH_PATH}"
        return {
            "source_id": self._source_id,
            "license": self._license,
            "source_ref": self._source_ref,
            "query": query,
            "texts": texts,
        }

    # -- extract ------------------------------------------------------------ #
    def extract(self, resolved: dict[str, Any]) -> bytes:
        """Consult the full text of each discovered décret; return them as JSON bytes.

        The output (``{"texts": [{id, cid, title, url, date, content}, …]}``) is the input to the
        deterministic text→entity candidate linker; it is also what ``snapshot`` persists for
        provenance/reproducibility.
        """
        texts = resolved.get("texts") or []
        if not texts:
            raise ValueError(
                "no LODA texts to extract — discover() returned an empty result set "
                f"(query {resolved.get('query')!r}). Refusing to snapshot an empty extract."
            )
        out: list[dict[str, Any]] = []
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
            token = self._mint_token(client)
            for index, text in enumerate(texts):
                if index:
                    _pause(PISTE_CONSULT_THROTTLE)  # pace consults under the free-tier rate limit
                consult = self._loda_consult(client, token, text["cid"], text.get("date"))
                out.append({**text, "content": _flatten_text(consult)})
        return json.dumps({EXTRACT_ENVELOPE_KEY: out}, ensure_ascii=False).encode("utf-8")

    # -- validate ----------------------------------------------------------- #
    def validate(self, raw: bytes, schema_ref: str | None) -> None:
        """Validate against any Table Schema (skipped when none — Légifrance has no schema)."""
        validate_extract(raw, source_id=self._source_id, schema_ref=schema_ref)

    # -- snapshot ----------------------------------------------------------- #
    def snapshot(self, raw: bytes, source_id: str) -> str:
        """Persist a provenance-tagged snapshot of the (JSON) PISTE extract; return its path."""
        path = write_snapshot(
            raw,
            source_id=source_id,
            extracted_at=datetime.now(tz=UTC).isoformat(),
            source_ref=self._source_ref or LEGIFRANCE_API_BASE,
            license=self._license,
            schema_ref=None,
            fmt="json",
            record_path=EXTRACT_ENVELOPE_KEY,
        )
        return str(path)

    # -- stage -------------------------------------------------------------- #
    def stage(self, snapshot_uri: str, source_id: str) -> None:
        raise NotImplementedError(
            "Curated loading is a cross-source, provenance-scoped rebuild done after snapshots "
            "exist — see `ingestion.load` / `make load` (FSC-35), not a per-source stage()."
        )

    # -- internals ---------------------------------------------------------- #
    def _mint_token(self, client: httpx.Client) -> str:
        """OAuth2 client-credentials grant → cached bearer token. Fail loud without credentials."""
        if self._token:
            return self._token
        if not self.has_credentials:
            raise RuntimeError(_MISSING_CREDS_MSG)
        resp = _request_with_retry(
            client,
            "POST",
            PISTE_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": PISTE_SCOPE,
            },
        )
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("PISTE token response carried no access_token")
        self._token = str(token)
        return self._token

    @staticmethod
    def _loda_search(client: httpx.Client, token: str, query: str) -> dict[str, Any]:
        """POST the LODA search for décrets (NATURE=DECRET), newest first. Authenticated."""
        body = {
            "recherche": {
                "champs": [
                    {
                        "typeChamp": "TITLE",
                        "criteres": [
                            {
                                "typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP",
                                "valeur": query,
                                "operateur": "ET",
                            }
                        ],
                        "operateur": "ET",
                    }
                ],
                "filtres": [{"facette": "NATURE", "valeurs": ["DECRET"]}],
                "pageNumber": 1,
                "pageSize": SEARCH_PAGE_SIZE,
                "sort": "SIGNATURE_DATE_DESC",
                "typePagination": "DEFAUT",
            },
            "fond": "LODA_DATE",
        }
        resp = _request_with_retry(
            client,
            "POST",
            f"{LEGIFRANCE_API_BASE}{LODA_SEARCH_PATH}",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.json()

    @staticmethod
    def _loda_consult(
        client: httpx.Client, token: str, cid: str, date: str | None
    ) -> dict[str, Any]:
        """Consult a LODA text by its chronical id at a given (or current) version date."""
        body = {"textId": cid, "date": date or datetime.now(tz=UTC).date().isoformat()}
        resp = _request_with_retry(
            client,
            "POST",
            f"{LEGIFRANCE_API_BASE}{LODA_CONSULT_PATH}",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.json()


def _decree_query(source: dict[str, Any]) -> str:
    """Derive the search query from the registry ``discovery.strategy``, else the default phrase."""
    strategy = str((source.get("discovery") or {}).get("strategy", ""))
    match = _PAREN_RE.search(strategy)
    if match and "décret" in match.group(1).lower():
        return match.group(1).strip()
    return DEFAULT_DECREE_QUERY


def _parse_search_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Map a LODA payload to ``[{id, cid, title, url, date}]`` — ids from the API, never frozen."""
    texts: list[dict[str, Any]] = []
    for result in payload.get("results", []) or []:
        titles = result.get("titles") or []
        if not titles:
            continue
        head = titles[0]
        cid = head.get("cid") or head.get("id")
        if not cid:
            continue
        texts.append(
            {
                "id": head.get("id") or cid,
                "cid": cid,
                "title": str(head.get("title") or "").strip(),
                "date": head.get("datePubli") or head.get("dateSignature"),
                "url": _permalink(cid),
            }
        )
    return texts


def _permalink(cid: str) -> str:
    """Public Légifrance permalink for a text id: /jorf/id/ for JORF texts, else /loda/id/."""
    base = LEGIFRANCE_JORF_BASE if cid.upper().startswith("JORF") else LEGIFRANCE_LODA_BASE
    return f"{base}/{cid}"


def _flatten_text(consult: dict[str, Any]) -> str:
    """Flatten a LODA consult response to plain text (title + article bodies, HTML stripped)."""
    parts: list[str] = []
    title = consult.get("title")
    if title:
        parts.append(str(title))
    for article in consult.get("articles", []) or []:
        content = article.get("content") or article.get("texte") or ""
        if content:
            parts.append(_strip_html(str(content)))
    body = consult.get("text") or consult.get("texteHtml")
    if body:
        parts.append(_strip_html(str(body)))
    return "\n".join(parts).strip()


def _strip_html(value: str) -> str:
    """Drop HTML tags and collapse whitespace — Légifrance article bodies are HTML fragments."""
    return _WS_RE.sub(" ", _HTML_TAG_RE.sub(" ", value)).strip()
