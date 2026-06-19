"""Transform OFGL local-authority balances into local budget facts + entities (FSC-32).

The OFGL (Observatoire des finances et de la gestion publique locales) publishes normalised
*agrégats comptables* for collectivités — one row per (collectivité, exercice, agrégat) carrying a
``Montant`` in euros, keyed on the collectivité's SIREN (and code INSEE). This is the **M57/M14**
accounting universe, distinct from the State's LOLF (mission/programme, AE/CP) — so the facts are
stamped ``nomenclature=m57`` and the anti-double-counting methodology (FSC-42) keeps them from being
silently summed with State credits.

**Anti-double-counting within OFGL (golden rule #8).** OFGL agrégats overlap: "Dépenses totales" is
"Dépenses de fonctionnement" + "Dépenses d'investissement". We therefore ingest only the **curated,
mutually-exclusive expenditure pair** below — their sum is the collectivité's total real spend with
no double-count. Recettes and encours de dette are deliberately excluded for now (summing them into
one "budget total" would double-count flows or mix a stock with flows). The agrégat labels are
OFGL's; **à confirmer** against the live dataset vocabulary during the spike.

SIREN is the canonical key: a row whose SIREN does not resolve is **counted in the report**
(golden rule #5), never guessed and never silently dropped. Pure — persistence is the loader's job;
columns are matched by **pattern** (labels drift), never frozen positions (mirrors the State-budget
transforms).
"""

from __future__ import annotations

import unicodedata

from core.models import BudgetFact, Entity, Level, Nomenclature
from core.resolve import normalize_siren

from ..tabular import first_column
from . import TransformResult, register_transform
from .budget_common import EXERCICE_PATTERNS, clean_cell, parse_amount, parse_year

SOURCE_ID = "finances_locales_ofgl"

# Column detection (OFGL ODS export labels; match by pattern, never a frozen header). `^montant$`
# first so the euro figure is taken over `Euros par habitant`/ratio columns.
_SIREN_PATTERNS = (r"\bsiren\b", r"siren")
# Prefer the collectivité's OWN name — commune/département/région — over `lbudg`, which is a
# budget-unit label ("PLANCHE DES BELLES FILLES- DEPT 70"), not the entity name. Ordered
# most-specific first: in the départements base both dep_name and reg_name exist, so dep_name (the
# collectivité itself) must win over reg_name (its parent). lbudg stays a last-resort fallback. The
# bare token is word-bounded so it never grabs `nomenclature`/`nombre`.
_NAME_PATTERNS = (
    r"^com.?name$",
    r"nom.?commune",
    r"^dep.?name$",
    r"^reg.?name$",
    r"nom.?coll",
    r"denom",
    r"lbudg",
    r"\bnom\b",
)
_AGREGAT_PATTERNS = (r"agr[ée]gat", r"libell")
_MONTANT_PATTERNS = (r"^montant$", r"\bmontant\b")
_CATEGORY_PATTERNS = (r"cat[ée]gorie", r"\bcat[ée]g\b", r"\bcat\b", r"niveau")

# Curated, mutually-exclusive expenditure agrégats (normalised, see `_norm`): fonctionnement +
# investissement partition real spending, so their sum is the collectivité's total spend with no
# double-count. Extend deliberately — adding an overlapping agrégat re-introduces double-counting.
_EXPENDITURE_AGREGATS: frozenset[str] = frozenset(
    {
        "depenses de fonctionnement",
        "depenses d'investissement",
    }
)


def _norm(value: str) -> str:
    """Accent-fold + lowercase + collapse whitespace for a stable agrégat-label comparison."""
    folded = unicodedata.normalize("NFKD", value.replace("’", "'"))
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


def build(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Pure transform: OFGL agrégat rows → local entities + ``m57`` budget facts + a report."""
    siren_col = first_column(headers, _SIREN_PATTERNS)
    exercice_col = first_column(headers, EXERCICE_PATTERNS)
    agregat_col = first_column(headers, _AGREGAT_PATTERNS)
    montant_col = first_column(headers, _MONTANT_PATTERNS)
    missing = [
        name
        for name, col in (
            ("siren", siren_col),
            ("exercice", exercice_col),
            ("agregat", agregat_col),
            ("montant", montant_col),
        )
        if col is None
    ]
    if missing:
        raise ValueError(f"OFGL: required column(s) {missing} not found in headers {headers!r}")
    assert siren_col and exercice_col and agregat_col and montant_col  # narrowed by the guard
    name_col = first_column(headers, _NAME_PATTERNS)
    category_col = first_column(headers, _CATEGORY_PATTERNS)

    entities_by_siren: dict[str, Entity] = {}
    facts: list[BudgetFact] = []
    considered = 0  # rows in the curated agrégat allowlist (the resolution-rate denominator)
    resolved = 0
    unresolved = 0
    dropped_no_exercice = 0
    skipped_agregat = 0

    for row in rows:
        agregat = clean_cell(row, agregat_col)
        if agregat is None or _norm(agregat) not in _EXPENDITURE_AGREGATS:
            skipped_agregat += 1  # outside the curated, non-overlapping set — not double-counted
            continue
        considered += 1
        siren = normalize_siren(row.get(siren_col))
        if siren is None:  # no usable SIREN -> reported, never guessed (golden rule #5)
            unresolved += 1
            continue
        resolved += 1
        exercice = parse_year(row.get(exercice_col))
        if exercice is None:  # no usable year -> the row cannot form a fact; surfaced in the report
            dropped_no_exercice += 1
            continue
        name = clean_cell(row, name_col) or siren
        entities_by_siren.setdefault(
            siren,
            Entity(
                siren=siren,
                name=name,
                level=Level.local,
                category=clean_cell(row, category_col),
                provenance=SOURCE_ID,
            ),
        )
        facts.append(
            BudgetFact(
                entity_siren=siren,
                exercice=exercice,
                mission=None,  # LOLF mission/programme do not apply to the M57 universe
                programme=agregat,  # the OFGL agrégat label is the within-nomenclature class
                amount_ae_eur=None,  # OFGL is cash-basis: no AE/CP split
                amount_cp_eur=parse_amount(row.get(montant_col)),
                executed=True,  # balances are realised, not voted
                nomenclature=Nomenclature.m57,
                provenance=SOURCE_ID,
            )
        )

    entities = sorted(entities_by_siren.values(), key=lambda e: e.siren or "")
    report = {
        "source_id": SOURCE_ID,
        "rows_in": len(rows),
        "facts_out": len(facts),
        "entities_out": len(entities),
        "skipped_agregat": skipped_agregat,
        "unresolved_siren": unresolved,
        "dropped_no_exercice": dropped_no_exercice,
        "resolution_rate": (resolved / considered) if considered else 0.0,
        "exercices": sorted({f.exercice for f in facts}),
        "agregats": sorted({f.programme for f in facts if f.programme}),
    }
    return TransformResult(entities=entities, budget_facts=facts, report=report)


@register_transform(SOURCE_ID)
def transform(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Registered entry point: OFGL agrégat rows → local entities + ``m57`` budget facts."""
    return build(headers, rows)
