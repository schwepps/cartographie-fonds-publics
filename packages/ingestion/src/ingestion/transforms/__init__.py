"""Per-source curated transforms: a snapshot's rows -> validated graph rows / budget facts.

The connector half (``connectors/``) is source-agnostic — discover/extract/validate/snapshot is the
same for every source on a given platform. The *curation* (which columns become entities, what edges
they imply, how SIRENs resolve, which rows are budget facts) is source-specific, so it lives here,
one module per source, keyed by the registry ``source_id``. A transform self-registers with
``@register_transform("<id>")``; FSC-35 (the loader) will look one up by source_id and hand its
output to Supabase.

A transform never writes anywhere — it returns a :class:`TransformResult` (entities + edges +
budget facts + report). That keeps it pure and fully offline-testable, and leaves persistence to
FSC-35. A given source populates only the slices it owns (operators -> entities/edges; the State
budget -> budget facts); the rest stay empty.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.models import Attribution, BudgetFact, Contract, Edge, Entity, Mention

# A transform maps parsed (headers, rows) to a graph slice. Dependencies (crosswalk, ministry
# reference) are loaded inside the registered entry point so the registry stays uniform; the pure
# core builders take them as arguments for injectable, offline tests.
Transform = Callable[[list[str], list[dict[str, str]]], "TransformResult"]


@dataclass(frozen=True)
class TransformResult:
    """A curated slice: entities, edges, budget facts, and a JSON-serializable report.

    A source populates only the slices it owns — operators emit ``entities``/``edges``; the State
    budget emits ``budget_facts``; DECP emits ``contracts`` + ``delegates`` edges + delegated
    ``entities``; the attributions source emits ``attributions``; the oversight source emits
    ``mentions``; the rest stay empty. ``report`` carries per-source counts (and, where applicable,
    the resolution rate + unresolved backlog — golden rule #5: never drop, never guess, report the
    match rate). Every input row is accounted for in a slice or the report.
    """

    entities: list[Entity] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    budget_facts: list[BudgetFact] = field(default_factory=list)
    contracts: list[Contract] = field(default_factory=list)
    attributions: list[Attribution] = field(default_factory=list)
    mentions: list[Mention] = field(default_factory=list)
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
from . import budget_execution_mensuelle as budget_execution_mensuelle  # noqa: E402,F401
from . import budget_plf_lfi as budget_plf_lfi  # noqa: E402,F401
from . import comptes_sociaux as comptes_sociaux  # noqa: E402,F401
from . import cour_des_comptes as cour_des_comptes  # noqa: E402,F401
from . import decp_commande_publique as decp_commande_publique  # noqa: E402,F401
from . import epl_sem_spl as epl_sem_spl  # noqa: E402,F401
from . import finances_locales_ofgl as finances_locales_ofgl  # noqa: E402,F401
from . import legifrance_attributions as legifrance_attributions  # noqa: E402,F401
from . import operateurs_etat as operateurs_etat  # noqa: E402,F401

__all__ = [
    "Transform",
    "TransformResult",
    "register_transform",
    "get_transform",
]
