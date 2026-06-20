"""Generic connector for ``platform: datagouv_api`` sources (the data.gouv.fr catalog).

One connector serves every ``datagouv_api`` source (operators, DECP, budget, …): the access method
is identical — resolve the current dataset via the catalog (organisation/tag/millésime, **never a
frozen slug**, golden rule #2), download the primary CSV, validate against any declared Table
Schema, and snapshot the raw bytes with provenance. Source-specific curation lives in
``ingestion.transforms``, keyed by source_id — not here — so this stays source-agnostic.

The discover→extract context (resolved resource URL, the source's license + schema ref) is held as
instance state and threaded into ``snapshot``, per the :class:`~ingestion.connectors.base.Connector`
contract. ``stage`` is intentionally not implemented here — curated loading is a cross-source,
provenance-scoped rebuild (``ingestion.load`` / ``make load``, FSC-35), not a per-source step.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from ..errors import SnapshotError
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
        self._resource_format: str | None = None  # data.gouv format of the selected resource
        self._max_bytes: int = MAX_RESOURCE_BYTES  # per-source download ceiling (registry override)
        self._cell_warnings: int = 0

    # -- discover ----------------------------------------------------------- #
    def discover(self, source: dict[str, Any]) -> dict[str, Any]:
        """Resolve the latest dataset + its primary resource for a registry source.

        A source may declare ``preferred_format`` (e.g. DECP's ``parquet``, ~10x smaller than its
        CSV) and ``max_download_mb`` (raise the default head-sample bound for a source we ingest in
        full). Both stay in the registry — never hardcoded here (golden rule #1).
        """
        query = self._query_from_strategy(source)
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
            dataset = self._discover_dataset(client, query)
        preferred = str(source.get("preferred_format") or "").strip().lower() or None
        resource = self._select_resource(dataset, preferred_format=preferred)
        # Capture provenance from the registry source for snapshot().
        self._source_id = str(source.get("id") or self._source_id)
        self._license = source.get("license")
        schema = source.get("schema")
        self._schema_ref = schema.get("ref") if isinstance(schema, dict) else None
        self._resource_url = resource["url"]
        self._resource_format = str(resource.get("format") or "").strip().lower() or None
        max_mb = source.get("max_download_mb")
        self._max_bytes = int(max_mb) * 1_000_000 if max_mb else MAX_RESOURCE_BYTES
        return {
            "dataset_id": dataset.get("id"),
            "title": dataset.get("title"),
            "slug": dataset.get("slug"),
            "resource_url": resource["url"],
            "format": self._resource_format,
        }

    # -- extract ------------------------------------------------------------ #
    def extract(self, resolved: dict[str, Any]) -> bytes:
        """Download the resolved resource.

        CSV/JSON are bounded to a head sample for very large dumps (a trailing partial row is
        dropped so the CSV still parses). A ``parquet`` resource is binary — head-truncation
        corrupts it — so it is downloaded **in full**, failing loud if it exceeds the per-source
        ceiling rather than silently truncating.
        """
        url = resolved["resource_url"]
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
            if self._resource_format == "parquet":
                raw = self._download_full(client, url, self._max_bytes)
            else:
                raw = self._download_head(client, url, self._max_bytes)
        self._resource_url = url
        return raw

    # -- validate ----------------------------------------------------------- #
    def validate(self, raw: bytes, schema_ref: str | None) -> None:
        """Validate against the Table Schema; raise loudly on drift. Keep the cell-warning count.

        The validation format follows the selected resource: a parquet extract is checked
        structurally (column drift only, via its footer — see ``validation`` FSC-38).
        """
        report = validate_extract(
            raw,
            source_id=self._source_id,
            schema_ref=schema_ref,
            fmt=self._validate_fmt(self._resource_format),
        )
        self._cell_warnings = report.cell_warning_count
        # Pin provenance to what was actually validated, so the snapshot can't record a stale ref.
        self._schema_ref = schema_ref

    # -- snapshot ----------------------------------------------------------- #
    def snapshot(self, raw: bytes, source_id: str) -> str:
        """Persist the raw extract as a provenance-tagged Parquet snapshot; return its path.

        The snapshot format is derived from the *selected resource's* declared format — never
        assumed CSV. ``write_snapshot`` tabularises csv/json only, so a non-tabular resource (e.g.
        the Cour des comptes PDF/txt corpus surfaced by ``_select_resource``'s fallback) fails loud
        here rather than being silently parsed as CSV.
        """
        path = write_snapshot(
            raw,
            source_id=source_id,
            extracted_at=datetime.now(tz=UTC).isoformat(),
            source_ref=self._resource_url,
            license=self._license,
            schema_ref=self._schema_ref,
            cell_warnings=self._cell_warnings,
            fmt=self._snapshot_fmt(self._resource_format),
        )
        return str(path)

    @staticmethod
    def _snapshot_fmt(resource_format: str | None) -> str:
        """Map a data.gouv resource format to a snapshot format; fail loud on non-tabular.

        ``write_snapshot`` handles ``csv``/``json``/``parquet``. CSV (and an unknown/blank format —
        the historic default for the tabular sources) snapshots as csv; json/geojson as json;
        parquet as parquet (read straight through duckdb); any explicitly non-tabular format (pdf,
        txt, xlsx, zip…) raises, since parsing it as CSV would corrupt the snapshot. Such sources
        are curated editorially (the transform reads a reviewed file, not the snapshot); a dedicated
        non-tabular snapshot path is future work (FSC-38).
        """
        fmt = (resource_format or "").strip().lower()
        if fmt in ("", "csv"):
            return "csv"
        if fmt in ("json", "geojson"):
            return "json"
        if fmt == "parquet":
            return "parquet"
        raise SnapshotError(
            f"datagouv_api cannot snapshot a {fmt!r} resource — write_snapshot handles "
            "csv/json/parquet only. Non-tabular sources (e.g. the Cour des comptes PDF corpus) are "
            "curated editorially via their transform; a non-tabular snapshot path is FSC-38."
        )

    @staticmethod
    def _validate_fmt(resource_format: str | None) -> str:
        """Validation format for the selected resource — tolerant (never raises).

        Mirrors ``_snapshot_fmt`` for csv/json/parquet, but an unknown/non-tabular format maps to
        ``csv``: such sources declare no schema, so ``validate_extract`` returns early (skipped)
        before the format matters — keeping validation a no-op rather than a hard error.
        """
        fmt = (resource_format or "").strip().lower()
        if fmt == "parquet":
            return "parquet"
        if fmt in ("json", "geojson"):
            return "json"
        return "csv"

    # -- stage -------------------------------------------------------------- #
    def stage(self, snapshot_uri: str, source_id: str) -> None:
        raise NotImplementedError(
            "Curated loading is a cross-source, provenance-scoped rebuild done after snapshots "
            "exist — see `ingestion.load` / `make load` (FSC-35), not a per-source stage(). "
            "Wiring this connector's live discover->snapshot loop and calling the loader is FSC-38."
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
    def _select_resource(
        dataset: dict[str, Any], preferred_format: str | None = None
    ) -> dict[str, Any]:
        """Pick the primary resource — largest of the preferred format, else largest CSV, else any.

        ``preferred_format`` (registry-declared, e.g. DECP's ``parquet``) wins when the dataset
        offers it. Otherwise most sources are CSV (the largest by catalog filesize; annexes are
        smaller). The Cour des comptes oversight corpus (FSC-62) is only PDF/txt, and discovery just
        needs to snapshot *a* resource for provenance, so a non-CSV fallback keeps discovery working
        without weakening CSV sources — they always have a CSV, so the preference still selects it.
        """
        resources = dataset.get("resources", [])
        if not resources:
            raise ValueError(f"No resource in dataset {dataset.get('title')!r}.")

        def of_format(fmt: str) -> list[dict[str, Any]]:
            return [r for r in resources if str(r.get("format", "")).lower() == fmt]

        preferred = (preferred_format or "").strip().lower()
        candidates = (preferred and of_format(preferred)) or of_format("csv") or resources
        # Stable tie-break on id/url so equal-size, equal-mtime candidates resolve identically
        # run to run — discovery's whole point is a reproducible millésime pick.
        return max(
            candidates,
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

    @staticmethod
    def _download_full(client: httpx.Client, url: str, max_bytes: int) -> bytes:
        """Stream a resource in full; fail loud past ``max_bytes`` (never truncate a binary).

        Used for parquet (and any format where a head sample would corrupt the file). The ceiling is
        a safety bound, not a sampling cap: exceeding it raises, so a source that outgrew its budget
        is surfaced (raise ``max_download_mb`` in the registry) rather than silently half-ingested.

        Accumulates into a single ``bytearray`` (amortized growth, one final copy) rather than a
        list of chunks + ``join`` — bounded peak memory for a large (~hundreds of MB) parquet.
        """
        buf = bytearray()
        with client.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_bytes():
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    raise ValueError(
                        f"resource at {url} exceeds the {max_bytes:,}-byte ceiling — refusing to "
                        "truncate a binary resource. Raise max_download_mb in the registry."
                    )
        return bytes(buf)
