"""Generic connector for ``platform: ods_explore`` sources (Opendatasoft Explore API v2.1).

One connector serves every ODS source (budget execution today; OFGL / comptes sociaux later): the
access method is identical — read the dataset's records endpoint **from the registry** (never a
frozen URL in code, golden rule #2), resolve the latest millésime, download *that exercice's* CSV
export, validate against any declared Table Schema, and snapshot the raw bytes with provenance.
Source-specific curation lives in ``ingestion.transforms``, keyed by source_id — not here.

Unlike the annually re-slugged data.gouv PLF, an ODS dataset (e.g. *situation mensuelle de l'État*)
is a single perennial dataset that accrues months across exercices. So "resolve the latest
millésime" means: take the stable dataset endpoint from the registry, read back the most recent
``exercice`` present, then fetch the export **filtered to that exercice** (ODS ``where=``).
Filtering makes the resolution consequential — it bounds the download to one year (so the byte cap
is a guard, never a silent head-sample that would drop later months and corrupt the per-month grain)
and records the resolved exercice in snapshot provenance (the source_ref URL carries the filter).

``stage`` is intentionally left to FSC-35 (the Supabase loader), mirroring the datagouv connector.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from ..snapshot import write_snapshot
from ..validation import validate_extract
from . import Connector, register

MAX_RESOURCE_BYTES = 50_000_000  # cap the (exercice-filtered) export; fail loud past it, never trim
RECORDS_MAX_BYTES = 10_000_000  # cap the discovery sample body so a bad/huge endpoint can't OOM CI
HTTP_TIMEOUT = 30.0
RECORDS_SAMPLE_LIMIT = 100  # ODS caps records `limit` at 100 — enough to read back the exercice
USER_AGENT = "cartographie-fonds-publics/ingestion (+https://cartographie-fonds-publics.fr)"

# The exercice/year field in an ODS record (names drift across portals — match by pattern).
_MILLESIME_FIELD_PATTERNS = (r"exercice", r"ann[ée]e", r"\byear\b")
# Split an ODS records endpoint into base + dataset id: ``https://…/datasets/<id>/records``.
# Anchored on http(s) so a malformed hint (file://, internal host) fails loud, like resolve_schema.
_ENDPOINT_RE = re.compile(r"^(?P<base>https?://.+?)/datasets/(?P<dataset>[^/?]+)")


@register("ods_explore")
class OdsExploreConnector(Connector):
    """Discover/extract/validate/snapshot for any Opendatasoft Explore v2.1 source."""

    def __init__(self) -> None:
        self._source_id: str = "ods_explore"
        self._license: str | None = None
        self._schema_ref: str | None = None
        self._source_ref: str | None = None
        self._cell_warnings: int = 0

    # -- discover ----------------------------------------------------------- #
    def discover(self, source: dict[str, Any]) -> dict[str, Any]:
        """Resolve the CSV export filtered to the latest exercice present (no frozen URL)."""
        records_url, export_url = self._endpoints(source)
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
            results = self._sample_records(client, records_url)
        field, latest_exercice = self._resolve_exercice(results)
        if field is None or latest_exercice is None:
            # The connector's contract is "resolve latest exercice, then fetch that year". Without a
            # resolved exercice we'd fall back to an unfiltered multi-year export (unbounded, and
            # the snapshot would not record a millésime) — fail loud instead (drift/misconfig).
            raise ValueError(
                f"ods_explore source {source.get('id')!r}: could not resolve an exercice from the "
                f"records sample (field={field!r}, latest={latest_exercice!r}). The dataset must "
                "expose an exercice/année field; fix the source or extend the connector."
            )
        where = f"{field}={latest_exercice}"
        # Capture provenance from the registry source for snapshot(); the source_ref carries the
        # exercice filter so the snapshot self-documents which millésime it holds.
        self._source_id = str(source.get("id") or self._source_id)
        self._license = source.get("license")
        schema = source.get("schema")
        self._schema_ref = schema.get("ref") if isinstance(schema, dict) else None
        self._source_ref = self._with_where(export_url, where)
        return {
            "dataset_id": self._dataset_id_from(records_url),
            "records_url": records_url,
            "export_url": export_url,
            "where": where,
            "latest_exercice": latest_exercice,
        }

    # -- extract ------------------------------------------------------------ #
    def extract(self, resolved: dict[str, Any]) -> bytes:
        """Download the CSV export filtered to the resolved exercice; fail loud past the cap."""
        url = resolved["export_url"]
        where = resolved.get("where")
        params = {"where": where} if where else None
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
            raw = self._fetch_bounded(
                client, url, params=params, max_bytes=MAX_RESOURCE_BYTES, what="export"
            )
        self._source_ref = self._with_where(url, where)
        return raw

    # -- validate ----------------------------------------------------------- #
    def validate(self, raw: bytes, schema_ref: str | None) -> None:
        """Validate against the Table Schema; raise loudly on drift. Keep the cell-warning count.

        Budget execution declares ``schema: ods_fields`` (not a resolvable Table Schema), so
        ``validate_extract`` skips — the contract still holds for an ODS source that ships one.
        """
        report = validate_extract(raw, source_id=self._source_id, schema_ref=schema_ref)
        self._cell_warnings = report.cell_warning_count
        self._schema_ref = schema_ref  # pin provenance to what was actually validated

    # -- snapshot ----------------------------------------------------------- #
    def snapshot(self, raw: bytes, source_id: str) -> str:
        """Persist the raw extract as a provenance-tagged Parquet snapshot; return its path."""
        path = write_snapshot(
            raw,
            source_id=source_id,
            extracted_at=datetime.now(tz=UTC).isoformat(),
            source_ref=self._source_ref,
            license=self._license,
            schema_ref=self._schema_ref,
            cell_warnings=self._cell_warnings,
        )
        return str(path)

    # -- stage -------------------------------------------------------------- #
    def stage(self, snapshot_uri: str, source_id: str) -> None:
        raise NotImplementedError(
            "Supabase staging is owned by FSC-35 (the curated-graph loader); "
            "FSC-26 produces validated budget facts via ingestion.transforms."
        )

    # -- internals ---------------------------------------------------------- #
    @staticmethod
    def _endpoints(source: dict[str, Any]) -> tuple[str, str]:
        """Derive the records + CSV-export URLs from the registry ``endpoint_hint``, never a frozen
        URL in code. Fails loud (incl. a non-http hint) so a bad registry entry is obvious rather
        than silently hitting the wrong portal.
        """
        hint = str(source.get("endpoint_hint") or "").strip()
        match = _ENDPOINT_RE.match(hint)
        if not match:
            raise ValueError(
                f"ods_explore source {source.get('id')!r} needs an https 'endpoint_hint' shaped "
                f"like '.../api/explore/v2.1/catalog/datasets/<id>/records'; got {hint!r}. "
                "Fix the registry entry."
            )
        base, dataset = match.group("base"), match.group("dataset")
        records_url = f"{base}/datasets/{dataset}/records"
        export_url = f"{base}/datasets/{dataset}/exports/csv"
        return records_url, export_url

    @staticmethod
    def _dataset_id_from(records_url: str) -> str | None:
        match = _ENDPOINT_RE.match(records_url)
        return match.group("dataset") if match else None

    @staticmethod
    def _with_where(url: str, where: str | None) -> str:
        """The export URL with its exercice filter applied — the provenance-faithful source_ref."""
        return str(httpx.URL(url, params={"where": where})) if where else url

    def _sample_records(self, client: httpx.Client, records_url: str) -> list[dict[str, Any]]:
        """Read a bounded page of records to introspect fields + read back the latest exercice.

        Discovery should not redirect (``follow_redirects=False``, matching ``resolve_schema``), and
        the body is byte-capped so a misbehaving endpoint cannot OOM the runner.
        """
        raw = self._fetch_bounded(
            client,
            records_url,
            params={"limit": RECORDS_SAMPLE_LIMIT},
            max_bytes=RECORDS_MAX_BYTES,
            what="records sample",
            follow_redirects=False,
        )
        results = json.loads(raw).get("results", [])
        if not results:
            raise ValueError(f"ODS dataset returned no records at {records_url!r}.")
        return list(results)

    @classmethod
    def _resolve_exercice(cls, results: list[dict[str, Any]]) -> tuple[str | None, int | None]:
        """Detect the exercice/year field and the latest year across the sampled records."""
        field = next(
            (
                key
                for key in results[0]
                if any(re.search(p, key, re.I) for p in _MILLESIME_FIELD_PATTERNS)
            ),
            None,
        )
        if field is None:
            return None, None
        years = [year for r in results if (year := cls._as_year(r.get(field))) is not None]
        return field, (max(years) if years else None)

    @staticmethod
    def _as_year(value: Any) -> int | None:
        match = re.search(r"\b(19|20)\d{2}\b", str(value))
        return int(match.group()) if match else None

    @staticmethod
    def _fetch_bounded(
        client: httpx.Client,
        url: str,
        *,
        params: dict[str, Any] | None,
        max_bytes: int,
        what: str,
        follow_redirects: bool = True,
    ) -> bytes:
        """Stream a response, refusing (loudly) anything past ``max_bytes``.

        Unlike a head-sample, a partial ODS extract would silently drop later months/exercices and
        corrupt the transform's per-month grain — so an oversize body is a hard error, not a trim.
        ODS supports ``where=``/pagination, so the fix is to narrow the query, never to truncate.
        """
        chunks: list[bytes] = []
        total = 0
        with client.stream("GET", url, params=params, follow_redirects=follow_redirects) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(
                        f"ODS {what} exceeded {max_bytes} bytes at {url!r}; narrow it with an "
                        "exercice filter or pagination. Refusing a partial extract."
                    )
                chunks.append(chunk)
        return b"".join(chunks)
