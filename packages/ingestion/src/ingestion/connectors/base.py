"""Connector contract. One implementation per access method (datagouv_api, ods_explore, rest)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Connector(ABC):
    """Each step is isolated so a source change touches only its connector."""

    @abstractmethod
    def discover(self, source: dict[str, Any]) -> dict[str, Any]:
        """Resolve the current resource(s) via catalog API — never a frozen slug."""

    @abstractmethod
    def extract(self, resolved: dict[str, Any]) -> bytes:
        """Fetch raw bytes."""

    @abstractmethod
    def validate(self, raw: bytes, schema_ref: str | None) -> None:
        """Validate against Table Schema; raise loudly on drift.

        Implementations delegate to ``ingestion.validation.validate_extract`` and keep its
        ``ValidationReport`` (e.g. the cell-warning count) to thread into ``snapshot``.
        """

    @abstractmethod
    def snapshot(self, raw: bytes, source_id: str) -> str:
        """Persist raw extract with provenance; return snapshot path/URI.

        Implementations delegate to ``ingestion.snapshot.write_snapshot``, supplying the
        ``extracted_at`` / ``source_ref`` / ``license`` / ``schema_ref`` provenance from
        connector instance state (the discover/extract context), not from this signature.
        """

    @abstractmethod
    def stage(self, snapshot_uri: str, source_id: str) -> None:
        """Load curated rows from the snapshot into Supabase (service-role write)."""
