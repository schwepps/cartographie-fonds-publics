"""Transform the social-protection accounts (DREES / Urssaf / LFSS) into aggregated social budget
facts (FSC-34).

The "comptes de la protection sociale" report spending **by branche** (risque) — Maladie,
Accidents du travail-Maladies professionnelles, Vieillesse, Famille, Autonomie — in the **social**
accounting universe (LFSS), distinct from the State's LOLF (mission/programme, AE/CP) and the
collectivités' M57/M14. So the facts are stamped ``nomenclature=social``; the anti-double-counting
methodology (FSC-42) keeps them from being silently summed with State credits or local balances.

This is the **most autonomous, hardest-to-link layer** (registry ``volatility.notes``: "Traiter en
module agrégé"): branches are not SIREN entities, so ``entity_siren`` is ``None`` and this transform
emits **no entities and no edges** — the social layer is an aggregated module, deliberately not
woven into the entity graph.

**Anti-double-counting within the social accounts (golden rule #8).** The source mixes grains: a
branche figure, régime sub-rows that decompose it, and an "ensemble des branches" total that sums
them. To avoid multiplying the spend we emit **one fact per (exercice, branche)** from the curated
branche allowlist at the **consolidated grain** (``niveau`` = "tous régimes" when the source carries
a niveau/régime column) and **never sum rows together**: off-allowlist labels, régime sub-grains,
and any second consolidated figure for the same branche/year are each **counted in the report**
(``skipped_branche`` / ``skipped_subgrain`` / ``duplicate_grain``), never silently dropped or added
(golden rule #5). The branche / niveau vocabulary is the publisher's; **à confirmer** against the
live DREES dataset before freezing (mirrors the OFGL transform).

Pure: persistence is the loader's job; columns are matched by **pattern** (labels drift), never
frozen positions (mirrors the State-budget and OFGL transforms).
"""

from __future__ import annotations

import unicodedata

from core.models import BudgetFact, Nomenclature

from ..tabular import first_column
from . import TransformResult, register_transform
from .budget_common import EXERCICE_PATTERNS, clean_cell, parse_amount, parse_year

SOURCE_ID = "comptes_sociaux"

# Column detection (DREES/Urssaf ODS export labels; match by pattern, never a frozen header).
_BRANCHE_PATTERNS = (r"\bbranche\b", r"\brisque\b")
# `^montant$` first so the euro figure is taken over `Euros par habitant`/ratio columns; then the
# common social-accounts spend labels.
_MONTANT_PATTERNS = (r"^montant$", r"\bmontant\b", r"prestation", r"d[ée]pense", r"charge")
# Optional grain column: when present, restrict to the consolidated grain (see `_TOP_GRAIN`).
_NIVEAU_PATTERNS = (r"niveau", r"r[ée]gime", r"p[ée]rim[èe]tre")

# Curated branche allowlist (normalised, see `_norm`): the canonical Sécu branches. Their
# consolidated figures partition social spending, so summing ACROSS branches is double-count-free.
# Aggregates that sum branches ("ensemble des branches", "total") are deliberately excluded — adding
# one re-introduces double-counting. **à confirmer** against the live dataset vocabulary.
_BRANCHES: frozenset[str] = frozenset(
    {
        "maladie",
        "at-mp",
        "accidents du travail - maladies professionnelles",
        "vieillesse",
        "retraite",
        "famille",
        "autonomie",
    }
)

# Consolidated grain kept when the source ships a niveau/régime column: drop régime sub-rows that
# decompose a branche (summing them under the branche double-counts). **à confirmer** likewise.
_TOP_GRAIN: frozenset[str] = frozenset(
    {
        "tous regimes",
        "tous regimes confondus",
        "ensemble des regimes",
        "ensemble",
    }
)


def _norm(value: str) -> str:
    """Accent-fold + lowercase + collapse whitespace for a stable label comparison (as OFGL)."""
    folded = unicodedata.normalize("NFKD", value.replace("’", "'"))
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


def build(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Social-accounts rows → aggregated ``social`` budget facts (by branche), plus a report."""
    branche_col = first_column(headers, _BRANCHE_PATTERNS)
    exercice_col = first_column(headers, EXERCICE_PATTERNS)
    montant_col = first_column(headers, _MONTANT_PATTERNS)
    missing = [
        name
        for name, col in (
            ("branche", branche_col),
            ("exercice", exercice_col),
            ("montant", montant_col),
        )
        if col is None
    ]
    if missing:
        raise ValueError(
            f"comptes_sociaux: required column(s) {missing} not found in headers {headers!r}"
        )
    assert branche_col and exercice_col and montant_col  # narrowed by the guard
    niveau_col = first_column(headers, _NIVEAU_PATTERNS)

    # One fact per (exercice, branche): the grain guard already keeps a single consolidated figure
    # per branche, so we do NOT sum — a second row for the same branche/year is a data anomaly (a
    # restated/synonym total) counted in `duplicate_grain`, never added (golden rule #8). The raw
    # label (cleaned) is kept as `programme`, mirroring OFGL's agrégat handling.
    by_key: dict[tuple[int, str], float] = {}
    considered = 0  # rows in the curated branche allowlist at the consolidated grain (denominator)
    skipped_branche = 0  # off the curated branche allowlist
    skipped_subgrain = 0  # an allowlisted branche but a régime sub-grain (would double-count)
    dropped_no_exercice = 0
    dropped_no_amount = 0
    duplicate_grain = 0  # a second consolidated figure for an already-seen (exercice, branche)

    for row in rows:
        label = clean_cell(row, branche_col)
        if label is None or _norm(label) not in _BRANCHES:
            skipped_branche += 1  # outside the curated branche set
            continue
        if niveau_col is not None:
            niveau = clean_cell(row, niveau_col)
            if niveau is not None and _norm(niveau) not in _TOP_GRAIN:
                # régime decomposition — summing it under the branche would double-count
                skipped_subgrain += 1
                continue
        considered += 1
        exercice = parse_year(row.get(exercice_col))
        if exercice is None:  # no usable year -> the row cannot form a fact; surfaced in the report
            dropped_no_exercice += 1
            continue
        amount = parse_amount(row.get(montant_col))
        if amount is None:  # no usable amount -> reported, never silently dropped (golden rule #5)
            dropped_no_amount += 1
            continue
        key = (exercice, label)
        if key in by_key:  # already have this branche/year at top grain -> anomaly, not summed
            duplicate_grain += 1
            continue
        by_key[key] = amount

    facts = [
        BudgetFact(
            entity_siren=None,  # social branches are not SIREN entities (aggregated module)
            exercice=exercice,
            mission=None,  # LOLF mission/programme do not apply to the social universe
            programme=branche,  # the branche label is the within-nomenclature class
            amount_ae_eur=None,  # social accounts are cash flows: no AE/CP split
            amount_cp_eur=amount,
            executed=True,  # the comptes are realised, not voted
            nomenclature=Nomenclature.social,
            provenance=SOURCE_ID,
        )
        for (exercice, branche), amount in sorted(
            by_key.items(), key=lambda kv: (kv[0][0], kv[0][1])
        )
    ]
    contributing = considered - dropped_no_exercice - dropped_no_amount - duplicate_grain
    report = {
        "source_id": SOURCE_ID,
        "rows_in": len(rows),
        "facts_out": len(facts),
        "skipped_branche": skipped_branche,
        "skipped_subgrain": skipped_subgrain,
        "dropped_no_exercice": dropped_no_exercice,
        "dropped_no_amount": dropped_no_amount,
        "duplicate_grain": duplicate_grain,
        "resolution_rate": (contributing / considered) if considered else 0.0,
        "branches": sorted({f.programme for f in facts if f.programme}),
        "exercices": sorted({f.exercice for f in facts}),
    }
    return TransformResult(budget_facts=facts, report=report)


@register_transform(SOURCE_ID)
def transform(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Registered entry point: social-accounts rows → aggregated ``social`` facts (by branche)."""
    return build(headers, rows)
