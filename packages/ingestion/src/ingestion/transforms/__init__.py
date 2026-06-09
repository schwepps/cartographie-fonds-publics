"""Per-source curated transforms: a snapshot's rows -> validated ``Entity``/``Edge`` graph rows.

The connector half (``connectors/``) is source-agnostic — discover/extract/validate/snapshot is the
same for every ``datagouv_api`` source. The *curation* (which columns become entities, what edges
they imply, how SIRENs resolve) is source-specific, so it lives here, one module per source, keyed
by the registry ``source_id``. A transform self-registers with ``@register_transform("<id>")``;
FSC-35 (the loader) will look one up by source_id and hand its output to Supabase.

A transform never writes anywhere — it returns a :class:`TransformResult` (entities + edges +
report). That keeps it pure and fully offline-testable, and leaves persistence to FSC-35.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.models import Edge, Entity

# A transform maps parsed (headers, rows) to a graph slice. Dependencies (crosswalk, ministry
# reference) are loaded inside the registered entry point so the registry stays uniform; the pure
# core builders take them as arguments for injectable, offline tests.
Transform = Callable[[list[str], list[dict[str, str]]], "TransformResult"]


@dataclass(frozen=True)
class TransformResult:
    """A curated graph slice: entities, edges, and a JSON-serializable resolution report.

    ``report`` carries the resolution rate + the unresolved backlog (golden rule #5: never drop,
    never guess, report the match rate). Every input operator is accounted for here or in an entity.
    """

    entities: list[Entity] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)


_TRANSFORMS: dict[str, Transform] = {}


def register_transform(source_id: str) -> Callable[[Transform], Transform]:
    """Bind a transform callable to a registry ``source_id`` (fails loud on a duplicate)."""

    def _decorator(fn: Transform) -> Transform:
        existing = _TRANSFORMS.get(source_id)
        if existing is not None and existing is not fn:
            raise ValueError(
                f"Duplicate transform for source_id {source_id!r}: "
                f"{existing.__module__}.{existing.__qualname__} vs "
                f"{fn.__module__}.{fn.__qualname__}"
            )
        _TRANSFORMS[source_id] = fn
        return fn

    return _decorator


def get_transform(source_id: str) -> Transform:
    """Return the transform registered for ``source_id``; fail loud if none."""
    fn = _TRANSFORMS.get(source_id)
    if fn is None:
        known = ", ".join(sorted(_TRANSFORMS)) or "(none registered)"
        raise KeyError(f"No transform registered for source_id {source_id!r}. Known: {known}.")
    return fn


# Import side-effecting modules so their @register_transform calls run. Append one line per source.
from . import operateurs_etat as operateurs_etat  # noqa: E402,F401

__all__ = [
    "Transform",
    "TransformResult",
    "register_transform",
    "get_transform",
]
