"""Transform the social-protection accounts (DREES « Comptes de la protection sociale », dataset
305) into aggregated social budget facts (FSC-34).

The comptes report social spending along **two hierarchies**: a *risque* (prestation) dimension —
Santé, Vieillesse-survie, Famille, Emploi, Logement, Pauvreté-exclusion sociale — and a *secteur
institutionnel* (régime) dimension. They live in the **social** accounting universe (LFSS), distinct
from the State's LOLF (mission/programme, AE/CP) and the collectivités' M57/M14, so the facts are
stamped ``nomenclature=social``; the anti-double-counting methodology (FSC-42) keeps them from being
silently summed with State credits or local balances.

This is the **most autonomous, hardest-to-link layer** (registry ``volatility.notes``: "Traiter en
module agrégé"): risques are not SIREN entities, so ``entity_siren`` is ``None`` and this transform
emits **no entities and no edges** — the social layer is an aggregated module, deliberately not
woven into the entity graph.

**Anti-double-counting within the social accounts (golden rule #8).** Both hierarchies mix grains:
the prestation dimension has a grand total (``ps_niveau`` 0, "Prestations de protection sociale")
that sums the six risques, plus sub-levels that decompose each one; the régime dimension has a
"Total tous régimes" consolidation plus individual régimes that decompose it. To avoid multiplying
the spend we emit **one fact per (exercice, risque)** at the **consolidated grain** — the top level
(``ps_niveau == "1"``) of the **all-régimes** figure (``si_nom == "Total tous régimes"``) — and
**never sum rows together**. Every other row (the grand total, a risk sub-level, an individual
régime, an off-allowlist label, a second figure for the same risque/year) is **counted in the
report**, never silently dropped or added (golden rule #5). The risque / secteur vocabulary was
confirmed against the live DREES dataset (2026-06); amounts are published in **millions of euros**.

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

# Column detection (DREES ODS field names; match by pattern, never a frozen header).
_BRANCHE_PATTERNS = (r"\brisque\b", r"\bbranche\b")
# `^val$`/`^valeur$` first (the DREES amount column), then the generic social-spend labels.
_MONTANT_PATTERNS = (
    r"^val$",
    r"^valeur$",
    r"^montant$",
    r"\bmontant\b",
    r"prestation",
    r"d[ée]pense",
    r"charge",
)
# The prestation hierarchy level (``ps_niveau``) and the secteur-institutionnel name (``si_nom``):
# the two grain columns that pin the consolidated figure. Required — without them the
# anti-double-counting grain can't be established, so the transform fails loud (golden rule #3/#8).
_PRESTATION_NIVEAU_PATTERNS = (r"^ps[_ ]?niveau$", r"niveau.*prestation")
_SECTEUR_PATTERNS = (r"^si[_ ]?nom$", r"secteur.*institutionnel")

# The 6 DREES risques (normalised, see `_norm`): their consolidated figures partition social
# spending, so summing ACROSS them is double-count-free. The grand total ("prestations de protection
# sociale", ps_niveau 0) is deliberately excluded — it sums the six.
_RISQUES: frozenset[str] = frozenset(
    {
        "sante",
        "vieillesse-survie",
        "famille",
        "emploi",
        "logement",
        "pauvrete-exclusion sociale",
    }
)

# The kept grain: the top risk level of the all-régimes consolidation. Deeper prestation levels
# decompose a risque, and individual régimes decompose the consolidation — keeping either double-
# counts. (`_RISK_LEVEL` compares the raw ps_niveau cell; `_TOUS_REGIMES` the normalised si_nom.)
_RISK_LEVEL = "1"
_TOUS_REGIMES = "total tous regimes"

# DREES publishes amounts in MILLIONS of euros; the curated facts are stored in euros.
_MILLIONS = 1_000_000


def _norm(value: str) -> str:
    """Accent-fold + lowercase + collapse whitespace for a stable label comparison (as OFGL)."""
    folded = unicodedata.normalize("NFKD", value.replace("’", "'"))
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


def build(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """DREES rows → aggregated ``social`` facts (one per exercice × risque), plus a report."""
    branche_col = first_column(headers, _BRANCHE_PATTERNS)
    exercice_col = first_column(headers, EXERCICE_PATTERNS)
    montant_col = first_column(headers, _MONTANT_PATTERNS)
    niveau_col = first_column(headers, _PRESTATION_NIVEAU_PATTERNS)
    secteur_col = first_column(headers, _SECTEUR_PATTERNS)
    missing = [
        name
        for name, col in (
            ("risque", branche_col),
            ("exercice", exercice_col),
            ("montant", montant_col),
            ("prestation niveau", niveau_col),
            ("secteur", secteur_col),
        )
        if col is None
    ]
    if missing:
        raise ValueError(
            f"comptes_sociaux: required column(s) {missing} not found in headers {headers!r}"
        )
    assert branche_col and exercice_col and montant_col and niveau_col and secteur_col

    # One fact per (exercice, risque) at the consolidated grain — we do NOT sum, so a second figure
    # for an already-seen (exercice, risque) is an anomaly counted in `duplicate_grain`, never added
    # (golden rule #8). Keyed on the NORMALISED risque so casing/accent variants collapse to one.
    by_key: dict[tuple[int, str], tuple[str, float]] = {}  # (exercice, norm) -> (raw label, euros)
    considered = 0  # rows at the kept grain whose risque is in the allowlist (the denominator)
    skipped_branche = 0  # off the curated risque allowlist (incl. the grand total)
    skipped_subgrain = 0  # a régime sub-figure or a prestation sub-level (would double-count)
    dropped_no_exercice = 0
    dropped_no_amount = 0
    duplicate_grain = 0  # a second consolidated figure for an already-seen (exercice, risque)

    for row in rows:
        secteur = clean_cell(row, secteur_col)
        niveau = clean_cell(row, niveau_col)
        # Keep only the all-régimes consolidation at the top risk level; everything else is a finer
        # grain of a kept figure (golden rule #8) — counted, never summed.
        if (
            secteur is None
            or _norm(secteur) != _TOUS_REGIMES
            or niveau is None
            or niveau != _RISK_LEVEL
        ):
            skipped_subgrain += 1
            continue
        label = clean_cell(row, branche_col)
        norm_label = _norm(label) if label is not None else None
        if norm_label is None or norm_label not in _RISQUES:
            skipped_branche += 1  # outside the curated risque set (e.g. the grand total)
            continue
        assert label is not None  # narrowed: norm_label is set only when label is not None
        considered += 1
        exercice = parse_year(row.get(exercice_col))
        if exercice is None:  # no usable year -> the row cannot form a fact; surfaced in the report
            dropped_no_exercice += 1
            continue
        amount = parse_amount(row.get(montant_col))
        if amount is None:  # no usable amount -> reported, never silently dropped (golden rule #5)
            dropped_no_amount += 1
            continue
        key = (exercice, norm_label)
        if key in by_key:  # already have this risque/year at the consolidated grain -> anomaly
            duplicate_grain += 1
            continue
        by_key[key] = (label, round(amount * _MILLIONS, 2))  # millions -> euros; first label wins

    facts = [
        BudgetFact(
            entity_siren=None,  # social risques are not SIREN entities (aggregated module)
            exercice=exercice,
            mission=None,  # LOLF mission/programme do not apply to the social universe
            programme=label,  # the (first-seen) risque label is the within-nomenclature class
            amount_ae_eur=None,  # social accounts are cash flows: no AE/CP split
            amount_cp_eur=amount,
            executed=True,  # the comptes are realised, not voted
            nomenclature=Nomenclature.social,
            provenance=SOURCE_ID,
        )
        for (exercice, _norm_risque), (label, amount) in sorted(
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
    """Registered entry point: DREES rows → aggregated ``social`` facts (by risque)."""
    return build(headers, rows)
