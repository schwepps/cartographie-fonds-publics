"""Connector contract + self-registering factory.

Append-only public surface: connector modules import ``register`` from
``ingestion.connectors.factory`` and never edit this file.
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
