"""Self-registering connector factory.

A connector binds itself to a registry ``platform`` with ``@register("<platform>")``;
``get_connector`` resolves a registry ``Source`` to its connector by ``source.platform``.
Adding a connector means dropping ONE module in this package — no edits to ``cli.py`` or
``connectors/__init__.py``, so connector tickets never collide on a shared file.

Connector modules must only *register* at import time — never call ``get_connector`` or do
other side effects at module top level, since auto-discovery imports every sibling module.
"""

from __future__ import annotations

import importlib
import pkgutil
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from ..errors import ConnectorImportError, UnknownPlatformError
from .base import Connector

if TYPE_CHECKING:
    from ..registry import Source

# Modules that are part of the machinery, not connectors — never auto-imported.
_SKIP_MODULES = frozenset({"base", "factory"})

_REGISTRY: dict[str, type[Connector]] = {}
_discovered = False
# Discovery mutates module globals; the lock keeps the one-time scan correct if a future
# caller invokes get_connector from multiple threads. The CLI today is single-threaded.
_discovery_lock = threading.Lock()


def register(platform: str) -> Callable[[type[Connector]], type[Connector]]:
    """Class decorator binding a ``Connector`` subclass to a registry ``platform`` string."""

    def _decorator(cls: type[Connector]) -> type[Connector]:
        existing = _REGISTRY.get(platform)
        if existing is not None and existing is not cls:
            raise ValueError(
                f"Duplicate connector for platform {platform!r}: "
                f"{existing.__module__}.{existing.__qualname__} vs "
                f"{cls.__module__}.{cls.__qualname__}"
            )
        _REGISTRY[platform] = cls
        return cls

    return _decorator


def _discover_connectors(package_name: str = __package__) -> None:
    """Import every sibling connector module so their ``@register`` calls run (idempotent).

    ``package_name`` is injectable so tests can drive the real scan over a temp package.
    A module that fails to import is re-raised as ``ConnectorImportError`` naming it, so one
    broken connector fails loud with attribution instead of an opaque traceback.
    """
    global _discovered
    if _discovered:
        return
    with _discovery_lock:
        if _discovered:
            return
        package = importlib.import_module(package_name)
        for info in pkgutil.iter_modules(package.__path__):
            name = info.name
            if name in _SKIP_MODULES or name.startswith("_"):
                continue
            try:
                importlib.import_module(f"{package_name}.{name}")
            except Exception as exc:
                raise ConnectorImportError(
                    f"Connector module {name!r} failed to import during discovery: {exc}"
                ) from exc
        _discovered = True


def get_connector(source: Source) -> Connector:
    """Instantiate the connector registered for ``source.platform``; fail loud if none."""
    _discover_connectors()
    platform = source.platform  # always str (Source.platform coerces); "" means missing/invalid
    if not platform:
        raise UnknownPlatformError(
            f"Source id={source.id!r} declares no usable platform; "
            f"every registry entry must set a non-empty string 'platform'."
        )
    cls = _REGISTRY.get(platform)
    if cls is None:
        known = ", ".join(sorted(_REGISTRY)) or "(none registered)"
        raise UnknownPlatformError(
            f"No connector registered for platform {platform!r} "
            f"(source id={source.id!r}). Known platforms: {known}."
        )
    return cls()
