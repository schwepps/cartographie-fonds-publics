"""Canonical domain model. SIREN is the primary join key across all layers."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator

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


class Level(str, Enum):
    state = "state"
    local = "local"
    social = "social"
    delegated = "delegated"


class EdgeType(str, Enum):
    tutelle = "tutelle"  # oversight / parent ministry
    participation = "participation"  # ownership stake (SEM/SPL)
    funds = "funds"  # money flow
    delegates = "delegates"  # public service delegation / contract


class Entity(BaseModel):
    siren: OptionalSiren  # canonical key; may be None until resolved
    name: str
    level: Level
    category: str | None = None  # INSEE legal category, operator category, etc.
    parent_siren: OptionalSiren = None


class Edge(BaseModel):
    source_siren: RequiredSiren
    target_siren: RequiredSiren
    type: EdgeType
    amount_eur: float | None = None
    exercice: int | None = None
    provenance: str | None = None  # source id from the registry


class BudgetFact(BaseModel):
    entity_siren: OptionalSiren
    exercice: int
    mission: str | None = None
    programme: str | None = None
    amount_ae_eur: float | None = None  # autorisations d'engagement
    amount_cp_eur: float | None = None  # credits de paiement
    executed: bool = False  # voted (False) vs executed (True)


class Contract(BaseModel):
    acheteur_siren: OptionalSiren
    titulaire_siren: OptionalSiren
    montant_eur: float | None = None
    nature: str | None = None  # marche | concession
    exercice: int | None = None


class Attribution(BaseModel):
    """Legal mandate / competence attributed to an entity (table: attributions)."""

    entity_siren: OptionalSiren = None
    legal_ref: str | None = None
    txt: str | None = None


class Mention(BaseModel):
    """Free-text mention of an entity in a report or document (table: mentions)."""

    entity_siren: OptionalSiren = None
    report_ref: str | None = None
    note: str | None = None
