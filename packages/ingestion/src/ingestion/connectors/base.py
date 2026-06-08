"""Connector contract. One implementation per access method (datagouv_api, ods, rest, file)."""

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
        """Validate against Table Schema; raise loudly on drift."""

    @abstractmethod
    def snapshot(self, raw: bytes, source_id: str) -> str:
        """Persist raw extract with provenance; return snapshot path/URI."""

    @abstractmethod
    def stage(self, snapshot_uri: str, source_id: str) -> None:
        """Load curated rows from the snapshot into Supabase (service-role write)."""
