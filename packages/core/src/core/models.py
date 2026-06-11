"""Frozen Phase-1 domain model. SIREN is the primary join key across all layers.

This module is the **stable contract** that every downstream connector and the Supabase
loader build against. It mirrors the business columns of ``supabase/migrations/0001_init.sql``
(entities, edges, budget_facts, contracts, attributions, mentions); the DB-generated ``id``
uuid primary keys are intentionally excluded (not a domain concern). Its enum vocabulary
mirrors the SQL ``CHECK`` constraints (``Level``, ``EdgeType``, ``Nature``).

**Frozen** means: do not edit field names, types, or enum values here as a one-off to make a
connector pass. Connectors consume this model read-only. A genuine schema change is a
coordinated change — a new numbered migration in ``supabase/migrations`` **and** a matching
update here in the same PR — never an ad-hoc edit on one side. All unknown fields are
rejected (``extra="forbid"``) so drift fails loud at construction.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict

from .resolve import normalize_siren


def _validate_siren(value: str | None) -> str | None:
    """Normalize a SIREN to 9 digits, or raise on a malformed non-empty value.

    None / empty is allowed (entities may be unresolved); anything else must be a
    valid SIREN since it is the primary join key across every layer.
    """
    if value is None or value == "":
        return None
    normalized = normalize_siren(value)
    if normalized is None:
        raise ValueError(f"invalid SIREN: {value!r}")
    return normalized


# Validated SIREN annotations: the optional form permits None (unresolved entities);
# the required form rejects None/empty after normalization.
OptionalSiren = Annotated[str | None, BeforeValidator(_validate_siren)]
RequiredSiren = Annotated[str, BeforeValidator(_validate_siren)]


class Level(StrEnum):
    state = "state"
    local = "local"
    social = "social"
    delegated = "delegated"


class EdgeType(StrEnum):
    tutelle = "tutelle"  # oversight / parent ministry
    participation = "participation"  # ownership stake (SEM/SPL)
    funds = "funds"  # money flow
    delegates = "delegates"  # public service delegation / contract


class Nature(StrEnum):
    marche = "marche"  # marché public
    concession = "concession"  # concession / DSP


class Nomenclature(StrEnum):
    """Accounting universe a budget fact belongs to — kept explicit so totals are never summed
    across universes silently (the anti-double-counting methodology, FSC-42)."""

    lolf = "lolf"  # State budget: mission > programme, AE/CP (budget_plf_lfi, budget_execution)
    m57 = "m57"  # local authorities (current accounting framework) — OFGL agrégats, cash basis
    m14 = "m14"  # local authorities (legacy framework, smaller communes)
    social = "social"  # social-security accounts (LFSS) — separate perimeter


class FrozenModel(BaseModel):
    """Base for the frozen domain model: unknown fields fail loud.

    Public (no underscore) because it is the shared base for the resolution layer too
    (``core.crosswalk``, ``core.resolution``), not just this module's domain models.
    """

    model_config = ConfigDict(extra="forbid")


class Entity(FrozenModel):
    siren: OptionalSiren  # canonical key; may be None until resolved
    name: str
    level: Level
    category: str | None = None  # INSEE legal category, operator category, etc.
    parent_siren: OptionalSiren = None
    provenance: str | None = None  # source id from the registry (mirrors Edge.provenance)


class Edge(FrozenModel):
    source_siren: RequiredSiren
    target_siren: RequiredSiren
    type: EdgeType
    amount_eur: float | None = None
    exercice: int | None = None
    provenance: str | None = None  # source id from the registry


class BudgetFact(FrozenModel):
    entity_siren: OptionalSiren
    exercice: int
    mission: str | None = None
    programme: str | None = None
    amount_ae_eur: float | None = None  # autorisations d'engagement
    amount_cp_eur: float | None = None  # credits de paiement
    executed: bool = False  # voted (False) vs executed (True)
    # accounting universe (LOLF / M57 / M14 / social) — see Nomenclature
    nomenclature: Nomenclature = Nomenclature.lolf
    provenance: str | None = None  # source id from the registry (mirrors Entity/Edge.provenance)


class Contract(FrozenModel):
    acheteur_siren: OptionalSiren
    titulaire_siren: OptionalSiren
    montant_eur: float | None = None
    nature: Nature | None = None
    exercice: int | None = None
    provenance: str | None = None  # source id from the registry (mirrors Entity/Edge.provenance)


class Attribution(FrozenModel):
    """Legal mandate / competence attributed to an entity (table: attributions)."""

    entity_siren: OptionalSiren = None
    legal_ref: str | None = None
    txt: str | None = None


class Mention(FrozenModel):
    """Free-text mention of an entity in a report or document (table: mentions)."""

    entity_siren: OptionalSiren = None
    report_ref: str | None = None
    note: str | None = None
