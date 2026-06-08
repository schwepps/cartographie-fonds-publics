"""Connector contract + self-registering factory.

Public surface for connectors: a connector module imports ``Connector`` and ``register``
from ``ingestion.connectors`` (this package) and self-registers — it never edits this file.
The re-export list below is append-only.
"""

from .base import Connector
from .factory import (
    ConnectorImportError,
    UnknownPlatformError,
    get_connector,
    register,
)

__all__ = [
    "Connector",
    "ConnectorImportError",
    "UnknownPlatformError",
    "get_connector",
    "register",
]
