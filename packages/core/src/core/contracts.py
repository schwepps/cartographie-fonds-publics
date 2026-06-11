"""Derive the curated graph slice (delegated entities + ``delegates`` edges) from contracts.

Pure domain logic shared by the DECP transform (``ingestion.transforms.decp_commande_publique``)
and the committed seed (``ingestion.seed``) so both produce delegates edges identically — a single
source of truth for the aggregation rule. Domain models in, domain models out; no I/O.

**Anti-double-counting convention (golden rule #8).** One ``delegates`` edge per
(acheteur, titulaire, exercice), with ``montant`` **summed** across that pair's contracts. The DECP
``montant`` is the *global* market amount, repeated on every co-titulaire / amendment row of a
market; the caller is responsible for collapsing a market to its current attribution and splitting
the amount equally among co-titulaires *before* building each :class:`Contract`, so summing here
never inflates the total. The residual cross-level double-counting (a euro counted at both the
funding and the delegation hop) is surfaced as a caveat in the Sankey UI, not silently netted.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from .models import Contract, Edge, EdgeType, Entity, Level, Nature

# Registry source id stamped as provenance on the rows derived from procurement contracts.
DECP_PROVENANCE = "decp_commande_publique"

# Human label per contract nature, used as the titulaire entity's ``category``.
_NATURE_CATEGORY: dict[Nature, str] = {
    Nature.marche: "Marché public",
    Nature.concession: "Concession",
}


def _category_for(natures: Iterable[Nature]) -> str | None:
    """A deterministic category label from a titulaire's contract natures (``None`` if empty)."""
    labels = sorted({_NATURE_CATEGORY[n] for n in natures})
    return " / ".join(labels) if labels else None


def aggregate_delegates_edges(
    contracts: Iterable[Contract],
    *,
    provenance: str = DECP_PROVENANCE,
) -> list[Edge]:
    """Aggregate contracts into ``delegates`` edges (acheteur → titulaire), summed per pair+year.

    Only contracts carrying a SIREN on **both** ends contribute — an :class:`Edge` requires one on
    each side, and a pair is the edge key. Contracts with an unresolved end are the caller's to
    report (golden rule #5); they are skipped here, never silently absorbed.

    A known amount (unknown ≠ zero): the edge sums the **known** montants of its contracts, and is
    ``None`` only when *every* contract for the pair has an unknown amount — never a misleading
    ``0.0``. The relationship still produces an edge (the delegation is real even if its value is
    unpublished). Output is sorted for deterministic SQL rendering.
    """
    # Track the running sum of known amounts per pair, and every pair seen (so an all-unknown pair
    # still yields an edge with amount_eur=None rather than being dropped or shown as 0).
    totals: dict[tuple[str, str, int | None], float] = {}
    seen: set[tuple[str, str, int | None]] = set()
    for contract in contracts:
        if contract.acheteur_siren is None or contract.titulaire_siren is None:
            continue
        key = (contract.acheteur_siren, contract.titulaire_siren, contract.exercice)
        seen.add(key)
        if contract.montant_eur is not None:
            totals[key] = totals.get(key, 0.0) + contract.montant_eur

    edges = [
        Edge(
            source_siren=acheteur,
            target_siren=titulaire,
            type=EdgeType.delegates,
            amount_eur=totals.get((acheteur, titulaire, exercice)),  # None if no known amount
            exercice=exercice,
            provenance=provenance,
        )
        for (acheteur, titulaire, exercice) in seen
    ]
    edges.sort(key=lambda e: (e.source_siren, e.target_siren, e.exercice or 0))
    return edges


def delegated_entities(
    contracts: Iterable[Contract],
    *,
    names: Mapping[str, str] | None = None,
    provenance: str = DECP_PROVENANCE,
) -> list[Entity]:
    """One ``level=delegated`` entity per titulaire SIREN (suppliers not yet in the graph).

    ``names`` maps titulaire SIREN → denomination (DECP carries ``titulaire_nom``); a
    titulaire with no known name falls back to its bare SIREN as the label, matching how the UI
    renders an unresolved party. ``category`` is derived from the set of natures the titulaire
    appears under. Buyer (acheteur) entities are intentionally **not** produced: acheteurs publics
    are owned by other layers (e.g. ``operateurs_etat``) and emitting them here could clobber their
    real ``level`` through the loader's upsert. Output is sorted by SIREN for determinism.
    """
    names = names or {}
    natures_by_titulaire: dict[str, set[Nature]] = defaultdict(set)
    for contract in contracts:
        if contract.titulaire_siren is None:
            continue
        if contract.nature is not None:
            natures_by_titulaire[contract.titulaire_siren].add(contract.nature)
        natures_by_titulaire.setdefault(contract.titulaire_siren, set())

    return [
        Entity(
            siren=siren,
            name=names.get(siren) or siren,
            level=Level.delegated,
            category=_category_for(natures),
            provenance=provenance,
        )
        for siren, natures in sorted(natures_by_titulaire.items())
    ]
