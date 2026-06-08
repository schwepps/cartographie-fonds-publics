"""Validate an extract against its declared Table Schema and fail loud on column drift.

Golden rule #3: validate every extract; fail loud on drift. The fail/pass decision keys on
*structural* drift — missing / extra / renamed columns, and any column whose declared type is
wrong on **every** row. Individual messy cells, unavoidable in open data such as DECP ("qualité
hétérogène"), are counted as warnings and never fatal, so one bad value cannot block a run.

Connector-agnostic on purpose: a future connector's ``validate()`` delegates here (see
``tests/connectors/README.md``). The one network hop — fetching a remote schema descriptor —
goes through httpx so the offline test harness (respx) can mock it.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx
from frictionless import Report, Resource, Schema

from .errors import SchemaResolutionError, SchemaValidationError

# frictionless tags marking a *structural* (column-level) problem — these are fatal drift.
_HEADER_TAGS = frozenset({"#header", "#label"})
# How many cell-warning samples to retain (for provenance / debugging).
_MAX_WARNING_SAMPLES = 10
_SCHEMA_FETCH_TIMEOUT = 30.0


@dataclass(frozen=True)
class ValidationReport:
    """Outcome of a passing validation. Returned so callers can record cell warnings."""

    source_id: str
    schema_ref: str | None
    skipped: bool  # True when no schema was declared -> nothing was validated
    cell_warning_count: int = 0
    cell_warning_samples: tuple[str, ...] = ()


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
            response = httpx.get(ref, timeout=_SCHEMA_FETCH_TIMEOUT)
            response.raise_for_status()
            descriptor = response.json()
        else:
            descriptor = json.loads(Path(ref).read_text(encoding="utf-8"))
        return Schema.from_descriptor(descriptor)
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
    on structural drift and ``SchemaResolutionError`` if the schema ref is unusable.
    """
    schema = resolve_schema(schema_ref)
    if schema is None:
        return ValidationReport(source_id, schema_ref, skipped=True)

    if fmt != "csv":
        # Only tabular CSV is validated for now; nested JSON envelopes are a separate concern.
        raise SchemaValidationError(
            source_id=source_id,
            schema_ref=schema_ref,
            other_issues=[f"unsupported extract format {fmt!r} (only 'csv' is validated)"],
        )

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
    total_rows = int(report.tasks[0].stats.get("rows") or 0) if report.tasks else 0

    missing: list[str] = []
    extra: list[str] = []
    renamed: list[str] = []
    other: list[str] = []
    type_errors: Counter[str] = Counter()
    row_errors: list[tuple[str, str, str]] = []  # (field, type, location)

    for etype, tags, field_name, row_number, note in report.flatten(
        ["type", "tags", "fieldName", "rowNumber", "note"]
    ):
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
            if etype == "type-error":
                type_errors[field_name] += 1
            row_errors.append((field_name, etype, f"row {row_number}"))
        else:
            # general / source / scheme / encoding errors -> structural, fatal
            other.append(f"{etype}: {note or field_name}")

    missing_set = set(missing)
    # A column whose declared type is wrong on EVERY data row is field-level type drift (fatal);
    # fewer bad cells are tolerated data-quality warnings.
    type_drift = sorted(
        f for f, c in type_errors.items() if total_rows and c >= total_rows and f not in missing_set
    )
    type_drift_set = set(type_drift)

    # Cell warnings exclude noise already explained by a fatal structural problem.
    warnings = [
        f"{loc} · {field or '?'} · {etype}"
        for (field, etype, loc) in row_errors
        if field not in missing_set and field not in type_drift_set
    ]

    if missing or extra or renamed or other or type_drift:
        raise SchemaValidationError(
            source_id=source_id,
            schema_ref=schema_ref,
            missing_columns=_dedupe(missing),
            extra_columns=_dedupe(extra),
            renamed_columns=_dedupe(renamed),
            type_drift_columns=type_drift,
            other_issues=other,
            cell_warning_count=len(warnings),
        )

    return ValidationReport(
        source_id,
        schema_ref,
        skipped=False,
        cell_warning_count=len(warnings),
        cell_warning_samples=tuple(warnings[:_MAX_WARNING_SAMPLES]),
    )


def _dedupe(items: Iterable[str]) -> list[str]:
    """Order-preserving de-duplication (a missing column can surface more than once)."""
    return list(dict.fromkeys(items))
