"""Anti-double-counting methodology: keep accounting universes explicit (FSC-42).

French public money is recorded in several *accounting universes* that are **not** consolidatable
into one total: the State budget (LOLF — mission/programme, AE/CP), local authorities (M57/M14 —
OFGL agrégats, cash basis), and the social-security accounts (LFSS). A euro can also be counted at
two hops of a funding chain (a subvention, then the recipient's onward spend). This module is the
single source of truth for the convention that the aggregation layer and the UI both apply:

* We never silently sum across universes. A total that **mixes** universes is an *order of
  magnitude*, surfaced with a methodology note — never presented as a consolidated figure.
* Within a universe, aggregation follows that source's documented grain (PLF: programme grain;
  DECP: market collapse + equal split among co-titulaires; OFGL: a curated, mutually-exclusive
  expenditure agrégat set).

The web mirrors this mapping in ``packages/web/src/lib/perimeter.ts`` (keyed on the entity *level*,
which is the universe proxy in the browser); this module — keyed on the authoritative
``BudgetFact.nomenclature`` — is the reference. See
``docs/adr/0007-anti-double-counting-state-local.md`` and golden rule #8.
"""

from __future__ import annotations

from collections.abc import Iterable

from .models import Level, Nomenclature

# Human labels for the distinct budget universes a fact/flow can belong to.
LOLF = "État (LOLF)"
M57 = "Collectivités (M57/M14)"
SOCIAL = "Sécurité sociale"

# Each accounting nomenclature maps to one universe (M57 and M14 are the same local universe).
_UNIVERSE_BY_NOMENCLATURE: dict[Nomenclature, str] = {
    Nomenclature.lolf: LOLF,
    Nomenclature.m57: M57,
    Nomenclature.m14: M57,
    Nomenclature.social: SOCIAL,
}

# Entity level → budget universe. ``delegated`` operators are *recipients* of public money, not a
# budget universe of their own, so they never by themselves make a total "mixed".
_UNIVERSE_BY_LEVEL: dict[Level, str | None] = {
    Level.state: LOLF,
    Level.local: M57,
    Level.social: SOCIAL,
    Level.delegated: None,
}


def universe_for_nomenclature(nomenclature: Nomenclature) -> str:
    """The accounting universe a budget fact belongs to (the authoritative mapping)."""
    return _UNIVERSE_BY_NOMENCLATURE[nomenclature]


def universe_for_level(level: Level) -> str | None:
    """The budget universe an entity's level implies; ``None`` for ``delegated`` (a recipient)."""
    return _UNIVERSE_BY_LEVEL[level]


def mixes_perimeters(items: Iterable[Nomenclature | Level]) -> bool:
    """True when ``items`` span more than one budget universe.

    A total computed over a mixed set must carry the methodology note rather than be read as a
    consolidated sum (FSC-42). Accepts nomenclatures (the authoritative key) and/or entity levels
    (``delegated`` contributes no universe, so it never alone triggers a mix).
    """
    universes: set[str] = set()
    for item in items:
        universe = (
            _UNIVERSE_BY_NOMENCLATURE[item]
            if isinstance(item, Nomenclature)
            else _UNIVERSE_BY_LEVEL[item]
        )
        if universe is not None:
            universes.add(universe)
    return len(universes) > 1
