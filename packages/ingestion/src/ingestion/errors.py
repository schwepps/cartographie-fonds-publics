"""Ingestion exception hierarchy. Catch ``IngestionError`` to handle any ingestion failure."""

from __future__ import annotations


class IngestionError(Exception):
    """Base for every error raised by the ingestion layer."""


class UnknownPlatformError(IngestionError):
    """No connector is registered for a source's ``platform``."""


class ConnectorImportError(IngestionError):
    """A connector module failed to import during auto-discovery."""
