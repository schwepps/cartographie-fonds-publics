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


def _validate_http_url(value: str | None) -> str | None:
    """Accept None/empty or an http(s) URL; reject any other scheme.

    Centralises the invariant the editorial loaders + the web fiche each enforce separately: a
    curated source link must be http(s) (golden rule #10 — verifiable provenance), so a
    ``javascript:``/``data:`` URL can never reach a stored row even from a future non-editorial
    producer (the FSC-66/67 scaling paths). Validates at the frozen-model boundary, the one contract
    every producer shares.
    """
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not value.lower().startswith(("http://", "https://")):
        raise ValueError(f"URL must be http(s): {value!r}")
    return value


# A source/reference URL: None/empty, or an http(s) URL (other schemes fail loud).
HttpUrlStr = Annotated[str | None, BeforeValidator(_validate_http_url)]


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


class MentionType(StrEnum):
    """What kind of Cour des comptes / CRTC publication an entity is mentioned in (FSC-62).

    Metadata-first oversight signal: a *rapport* (public/thematic report, observations
    définitives) vs a *recommandation* (a specific recommendation issued to the body). Mirrors the
    ``mentions.mention_type`` SQL ``CHECK``."""

    rapport = "rapport"  # public/thematic report, observations
    recommandation = "recommandation"  # a recommendation issued to the controlled body


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
    """Legal mandate / competence attributed to an entity (table: attributions, FSC-27).

    The "why" layer: a décret d'attribution (or LOLF text) that mandates an entity. ``legal_ref`` is
    the human reference (e.g. the JORF décret number) and ``source_url`` the real Légifrance link
    that backs it (golden rule #10 — every mandate links to a verifiable source)."""

    entity_siren: OptionalSiren = None
    legal_ref: str | None = None  # human legal reference (e.g. "Décret n° 2024-… du …")
    txt: str | None = None  # the competence / mandate text
    source_url: HttpUrlStr = None  # Légifrance/JORF URL backing the legal_ref (http(s) only)
    provenance: str | None = None  # source id from the registry (mirrors Entity/Edge.provenance)


class Mention(FrozenModel):
    """An entity mentioned in a Cour des comptes / CRTC publication (table: mentions, FSC-62).

    Metadata-first oversight signal (« épinglé par la Cour »): which report, when, what kind, the
    link, and a short note/excerpt. ``license`` is per-row because the audit corpus is not uniformly
    licensed (e.g. the published-recommendations dataset is ODbL, not the registry's default)."""

    entity_siren: OptionalSiren = None
    report_ref: str | None = None  # report title / reference
    report_date: str | None = None  # ISO date string (carried as text, like other dates)
    mention_type: MentionType | None = None
    url: HttpUrlStr = None  # source report URL (http(s) only)
    note: str | None = None  # short note / excerpt
    provenance: str | None = None  # source id from the registry (mirrors Entity/Edge.provenance)
    license: str | None = None  # per-row licence (audit corpus is not uniformly licensed)
