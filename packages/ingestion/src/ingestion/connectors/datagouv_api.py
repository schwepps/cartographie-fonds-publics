"""Generic connector for ``platform: datagouv_api`` sources (the data.gouv.fr catalog).

One connector serves every ``datagouv_api`` source (operators, DECP, budget, …): the access method
is identical — resolve the current dataset via the catalog (organisation/tag/millésime, **never a
frozen slug**, golden rule #2), download the primary CSV, validate against any declared Table
Schema, and snapshot the raw bytes with provenance. Source-specific curation lives in
``ingestion.transforms``, keyed by source_id — not here — so this stays source-agnostic.

The discover→extract context (resolved resource URL, the source's license + schema ref) is held as
instance state and threaded into ``snapshot``, per the :class:`~ingestion.connectors.base.Connector`
contract. ``stage`` is intentionally left to FSC-35 (the Supabase loader).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from ..snapshot import write_snapshot
from ..validation import validate_extract
from . import Connector, register

# The data.gouv.fr catalog host (platform infrastructure, mirrors ``platforms.datagouv_api.base`` in
# the registry) — not a dataset slug. Which dataset is always discovered dynamically.
DEFAULT_API_BASE = "https://www.data.gouv.fr/api/1"
MAX_RESOURCE_BYTES = 50_000_000  # bound a download (DECP's consolidated CSV is ~2 GB) — head sample
HTTP_TIMEOUT = 30.0
USER_AGENT = "cartographie-fonds-publics/ingestion (+https://cartographie-fonds-publics.fr)"

# Extract the search term from a registry ``discovery.strategy`` like search_datasets(query='…').
_QUERY_RE = re.compile(r"search_datasets\(\s*(?:query\s*=\s*)?['\"](.+?)['\"]\s*\)")


@register("datagouv_api")
class DatagouvApiConnector(Connector):
    """Discover/extract/validate/snapshot for any data.gouv.fr catalog source."""

    def __init__(self, api_base: str = DEFAULT_API_BASE) -> None:
        self._api_base = api_base.rstrip("/")
        self._source_id: str = "datagouv_api"
        self._license: str | None = None
        self._schema_ref: str | None = None
        self._resource_url: str | None = None
        self._cell_warnings: int = 0

    # -- discover ----------------------------------------------------------- #
    def discover(self, source: dict[str, Any]) -> dict[str, Any]:
        """Resolve the latest dataset + its primary CSV resource for a registry source."""
        query = self._query_from_strategy(source)
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
            dataset = self._discover_dataset(client, query)
        resource = self._select_csv_resource(dataset)
        # Capture provenance from the registry source for snapshot().
        self._source_id = str(source.get("id") or self._source_id)
        self._license = source.get("license")
        schema = source.get("schema")
        self._schema_ref = schema.get("ref") if isinstance(schema, dict) else None
        self._resource_url = resource["url"]
        return {
            "dataset_id": dataset.get("id"),
            "title": dataset.get("title"),
            "slug": dataset.get("slug"),
            "resource_url": resource["url"],
        }

    # -- extract ------------------------------------------------------------ #
    def extract(self, resolved: dict[str, Any]) -> bytes:
        """Download the resolved CSV resource (bounded to a head sample for very large dumps)."""
        url = resolved["resource_url"]
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
            raw = self._download_head(client, url, MAX_RESOURCE_BYTES)
        self._resource_url = url
        return raw

    # -- validate ----------------------------------------------------------- #
    def validate(self, raw: bytes, schema_ref: str | None) -> None:
        """Validate against the Table Schema; raise loudly on drift. Keep the cell-warning count."""
        report = validate_extract(raw, source_id=self._source_id, schema_ref=schema_ref)
        self._cell_warnings = report.cell_warning_count
        # Pin provenance to what was actually validated, so the snapshot can't record a stale ref.
        self._schema_ref = schema_ref

    # -- snapshot ----------------------------------------------------------- #
    def snapshot(self, raw: bytes, source_id: str) -> str:
        """Persist the raw extract as a provenance-tagged Parquet snapshot; return its path."""
        path = write_snapshot(
            raw,
            source_id=source_id,
            extracted_at=datetime.now(tz=UTC).isoformat(),
            source_ref=self._resource_url,
            license=self._license,
            schema_ref=self._schema_ref,
            cell_warnings=self._cell_warnings,
        )
        return str(path)

    # -- stage -------------------------------------------------------------- #
    def stage(self, snapshot_uri: str, source_id: str) -> None:
        raise NotImplementedError(
            "Supabase staging is owned by FSC-35 (the curated-graph loader); "
            "FSC-25 produces validated entities/edges via ingestion.transforms."
        )

    # -- internals ---------------------------------------------------------- #
    @staticmethod
    def _query_from_strategy(source: dict[str, Any]) -> str:
        """Derive the catalog search query from the registry ``discovery.strategy``."""
        strategy = str((source.get("discovery") or {}).get("strategy", ""))
        match = _QUERY_RE.search(strategy)
        if not match:
            raise ValueError(
                f"Could not derive a search query from discovery.strategy {strategy!r}. "
                "Fix the registry strategy string."
            )
        return match.group(1)

    def _discover_dataset(self, client: httpx.Client, query: str) -> dict[str, Any]:
        """Resolve the latest dataset for a query via the catalog. Fail loud on no result."""
        resp = client.get(
            f"{self._api_base}/datasets/",
            params={"q": query, "page_size": 100},
            follow_redirects=True,
        )
        resp.raise_for_status()
        datasets = resp.json().get("data", [])
        if not datasets:
            raise ValueError(f"No datasets returned for query {query!r}.")
        return self._latest_by_year(datasets) or datasets[0]

    @staticmethod
    def _latest_by_year(datasets: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Pick the dataset whose title carries the most recent 4-digit year (the millésime)."""
        best, best_year = None, -1
        for dataset in datasets:
            years = [int(y) for y in re.findall(r"\b(20\d{2})\b", dataset.get("title", ""))]
            year = max(years) if years else 0
            if year > best_year:
                best, best_year = dataset, year
        return best

    @staticmethod
    def _select_csv_resource(dataset: dict[str, Any]) -> dict[str, Any]:
        """Pick the primary CSV resource — the largest by catalog filesize (annexes are smaller)."""
        csvs = [
            r for r in dataset.get("resources", []) if str(r.get("format", "")).lower() == "csv"
        ]
        if not csvs:
            raise ValueError(f"No CSV resource in dataset {dataset.get('title')!r}.")
        # Stable tie-break on id/url so equal-size, equal-mtime candidates resolve identically
        # run to run — discovery's whole point is a reproducible millésime pick.
        return max(
            csvs,
            key=lambda r: (
                r.get("filesize") or 0,
                r.get("last_modified") or "",
                r.get("id") or r.get("url") or "",
            ),
        )

    @staticmethod
    def _download_head(client: httpx.Client, url: str, max_bytes: int) -> bytes:
        """Stream up to ``max_bytes``; on truncation drop the dangling partial row so CSV parses."""
        chunks: list[bytes] = []
        total = 0
        truncated = False
        with client.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_bytes():
                chunks.append(chunk)
                total += len(chunk)
                if total >= max_bytes:
                    truncated = True
                    break
        data = b"".join(chunks)
        if truncated:
            data = data[:max_bytes]
            cut = data.rfind(b"\n")
            if cut != -1:
                data = data[:cut]
        return data
