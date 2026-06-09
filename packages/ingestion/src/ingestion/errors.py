"""Ingestion exception hierarchy. Catch ``IngestionError`` to handle any ingestion failure."""

from __future__ import annotations

from collections.abc import Sequence


class IngestionError(Exception):
    """Base for every error raised by the ingestion layer."""


class UnknownPlatformError(IngestionError):
    """No connector is registered for a source's ``platform``."""


class ConnectorImportError(IngestionError):
    """A connector module failed to import during auto-discovery."""


class SchemaResolutionError(IngestionError):
    """A declared schema reference could not be fetched or parsed.

    This is a *configuration* fault (an unreachable or malformed ``schema.ref``), not data
    drift — kept separate so alerting can tell "our registry is wrong" from "the data changed".
    """


class UnsupportedFormatError(IngestionError):
    """An extract format the harness cannot process yet (e.g. JSON validation/snapshot).

    A *capability* limit, distinct from drift (``SchemaValidationError``) — so alerting never
    mistakes "we can't handle this format" for "the source changed".
    """


class SnapshotError(IngestionError):
    """Writing a raw-extract snapshot failed; the previous valid snapshot is left untouched."""


class LoadError(IngestionError):
    """The curated load was refused or failed — e.g. a source contributed zero rows, which would
    delete its existing curated rows (provenance-scoped rebuild) with nothing to re-insert. Fail
    loud rather than silently wipe the graph (golden rule #3)."""


class SchemaValidationError(IngestionError):
    """An extract drifted from its declared Table Schema — fail loud (golden rule #3).

    Carries the *structural* drift (missing / extra / renamed columns) so the message is
    actionable (AC2). Row-level cell issues — including wrong-typed values — are not fatal;
    their count is reported for context only (see ``validation.validate_extract``).
    """

    # Cap how many columns we spell out, so the message stays readable on very wide tables.
    _MAX_LISTED = 20

    def __init__(
        self,
        *,
        source_id: str,
        schema_ref: str | None,
        missing_columns: Sequence[str] = (),
        extra_columns: Sequence[str] = (),
        renamed_columns: Sequence[str] = (),
        other_issues: Sequence[str] = (),
        cell_warning_count: int = 0,
    ) -> None:
        self.source_id = source_id
        self.schema_ref = schema_ref
        self.missing_columns = list(missing_columns)
        self.extra_columns = list(extra_columns)
        self.renamed_columns = list(renamed_columns)
        self.other_issues = list(other_issues)
        self.cell_warning_count = cell_warning_count
        super().__init__(self._format())

    def _format(self) -> str:
        lines = [f"Schema drift for source {self.source_id!r} against schema {self.schema_ref!r}:"]
        if self.missing_columns:
            lines.append(f"  - missing columns: {self._join(self.missing_columns)}")
        if self.extra_columns:
            lines.append(f"  - unexpected columns: {self._join(self.extra_columns)}")
        if self.renamed_columns:
            lines.append(f"  - renamed / incorrect labels: {self._join(self.renamed_columns)}")
        lines.extend(f"  - {issue}" for issue in self.other_issues[: self._MAX_LISTED])
        if self.cell_warning_count:
            lines.append(
                f"  ({self.cell_warning_count} row-level cell warning(s) ignored — "
                f"not treated as drift)"
            )
        lines.append(
            "  Fix the source mapping, or update the registry schema ref if the change is intended."
        )
        return "\n".join(lines)

    @classmethod
    def _join(cls, cols: Sequence[str]) -> str:
        shown = list(cols)[: cls._MAX_LISTED]
        extra = len(cols) - cls._MAX_LISTED
        suffix = f" (+{extra} more)" if extra > 0 else ""
        return ", ".join(shown) + suffix
