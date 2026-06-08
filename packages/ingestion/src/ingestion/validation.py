"""Validate an extract against its declared Table Schema and fail loud on column drift.

Golden rule #3: validate every extract; fail loud on drift. The fail/pass decision keys on
**column-structure drift** — missing / extra / renamed columns (and unparseable extracts).
Row-level cell issues, *including wrong-typed values*, are counted as warnings and never fatal:
open data such as DECP is "qualité hétérogène", so one bad value (or a noisy column) must not
block a run. The warning count travels into the snapshot's provenance, where the registry's
monitoring (schema_conformity / row_count_delta) can act on a spike.

Connector-agnostic on purpose: a future connector's ``validate()`` delegates here (see
``tests/connectors/README.md``). The one network hop — fetching a remote schema descriptor —
goes through httpx so the offline test harness (respx) can mock it.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx
from frictionless import Report, Resource, Schema

from .errors import SchemaResolutionError, SchemaValidationError, UnsupportedFormatError

# frictionless tags marking a *structural* (column-level) problem — these are fatal drift.
_HEADER_TAGS = frozenset({"#header", "#label"})
_SCHEMA_FETCH_TIMEOUT = 30.0
_MAX_SCHEMA_BYTES = 5_000_000  # a Table Schema descriptor is small; cap so a bad ref can't OOM CI


@dataclass(frozen=True)
class ValidationReport:
    """Outcome of a passing validation. Returned so callers can record the cell-warning count."""

    source_id: str
    schema_ref: str | None
    skipped: bool  # True when no schema was declared -> nothing was validated
    cell_warning_count: int = 0


def resolve_schema(schema_ref: str | None) -> Schema | None:
    """Load a Table Schema descriptor from a URL or local path. ``None``/empty -> no schema.

    Raises ``SchemaResolutionError`` (a config fault, distinct from data drift) when the
    reference cannot be fetched or parsed.
    """
    if schema_ref is None:
        return None
    ref = schema_ref.strip()
    if not ref:
        return None
    try:
        if ref.startswith(("http://", "https://")):
            # httpx does not follow redirects by default; keep it explicit so a schema ref
            # cannot be bounced to an internal address, and cap the body so a bad ref can't OOM.
            response = httpx.get(ref, timeout=_SCHEMA_FETCH_TIMEOUT, follow_redirects=False)
            response.raise_for_status()
            if len(response.content) > _MAX_SCHEMA_BYTES:
                raise SchemaResolutionError(
                    f"Schema at {ref!r} exceeds {_MAX_SCHEMA_BYTES} bytes — refusing to load."
                )
            descriptor = response.json()
        else:
            descriptor = json.loads(Path(ref).read_text(encoding="utf-8"))
        return Schema.from_descriptor(descriptor)
    except SchemaResolutionError:
        raise
    except Exception as exc:  # noqa: BLE001 — re-raised as a typed, actionable error
        raise SchemaResolutionError(
            f"Could not resolve Table Schema for ref {schema_ref!r}: {exc}"
        ) from exc


def validate_extract(
    raw: bytes,
    *,
    source_id: str,
    schema_ref: str | None,
    fmt: str = "csv",
) -> ValidationReport:
    """Validate ``raw`` against the schema at ``schema_ref``. Raise loudly on column drift.

    Returns a ``ValidationReport`` when the extract conforms (possibly with non-fatal cell
    warnings), or when no schema is declared (``skipped=True``). Raises ``SchemaValidationError``
    on structural drift, ``SchemaResolutionError`` if the schema ref is unusable, and
    ``UnsupportedFormatError`` for a format the harness cannot validate yet.
    """
    schema = resolve_schema(schema_ref)
    if schema is None:
        return ValidationReport(source_id, schema_ref, skipped=True)

    if fmt != "csv":
        # A capability limit, not drift — keep it a distinct error so alerting never confuses
        # "we can't validate this format yet" with "the source changed".
        raise UnsupportedFormatError(f"Cannot validate format {fmt!r} yet (only 'csv').")

    try:
        report = Resource(raw, format=fmt, schema=schema).validate()
    except Exception as exc:  # noqa: BLE001 — a parse failure of the extract itself IS drift
        raise SchemaValidationError(
            source_id=source_id,
            schema_ref=schema_ref,
            other_issues=[f"extract could not be parsed as {fmt}: {exc}"],
        ) from exc

    if report.valid:
        return ValidationReport(source_id, schema_ref, skipped=False)

    return _classify(report, source_id=source_id, schema_ref=schema_ref)


def _classify(report: Report, *, source_id: str, schema_ref: str | None) -> ValidationReport:
    """Split a failed frictionless report into fatal column drift vs tolerable cell warnings."""
    missing: list[str] = []
    extra: list[str] = []
    renamed: list[str] = []
    other: list[str] = []
    cell_warnings = 0

    for etype, tags, field_name, note in report.flatten(["type", "tags", "fieldName", "note"]):
        tagset = set(tags or ())
        if tagset & _HEADER_TAGS:
            if etype == "missing-label":
                missing.append(field_name)
            elif etype == "extra-label":
                extra.append(field_name)
            elif etype == "incorrect-label":
                renamed.append(field_name)
            else:
                other.append(f"{etype}: {field_name}")
        elif tagset & {"#row", "#cell"}:
            cell_warnings += 1  # wrong-typed / missing / constraint cells -> warning, not drift
        else:
            # general / source / scheme / encoding errors (e.g. an unparseable extract) are fatal
            other.append(f"{etype}: {note or field_name}")

    if missing or extra or renamed or other:
        raise SchemaValidationError(
            source_id=source_id,
            schema_ref=schema_ref,
            missing_columns=_dedupe(missing),
            extra_columns=_dedupe(extra),
            renamed_columns=_dedupe(renamed),
            other_issues=other,
            cell_warning_count=cell_warnings,
        )

    return ValidationReport(source_id, schema_ref, skipped=False, cell_warning_count=cell_warnings)


def _dedupe(items: Iterable[str]) -> list[str]:
    """Order-preserving de-duplication (a missing column can surface more than once)."""
    return list(dict.fromkeys(items))
