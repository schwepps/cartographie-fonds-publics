"""Transform the "situation mensuelle de l'État" into executed budget facts (FSC-26).

The monthly execution dataset reports *réalisé* spending per mission/programme, one row per month.
Each month's figure is **cumulative year-to-date**, so this transform keeps, for every
``(exercice, mission, programme)``, the row with the **latest month** and emits one
:class:`~core.models.BudgetFact` with ``executed=True``.

**Anti-double-counting (golden rule #8).** Months are cumulative — summing them would multiply the
spend several-fold, so we take the latest month *only*, never a sum across months. (PLF/LFI, by
contrast, sums leaf actions to the programme grain.) This convention is fixed here and surfaces in
the UI methodology note. Dépenses map to ``amount_cp_eur`` (cash executed); ``amount_ae_eur`` is set
only if the source ships a distinct commitments column. Missions/programmes are not SIREN entities,
so ``entity_siren`` is ``None``.

Pure: persistence is FSC-35's job. Columns are matched by *pattern*, never a frozen header.
"""

from __future__ import annotations

from core.models import BudgetFact

from ..tabular import first_column
from . import TransformResult, register_transform
from .budget_common import (
    EXERCICE_PATTERNS,
    MISSION_PATTERNS,
    PROGRAMME_PATTERNS,
    clean_cell,
    parse_amount,
    parse_year,
)

SOURCE_ID = "budget_execution_mensuelle"

_PERIOD_PATTERNS = (r"\bmois\b", r"p[ée]riode", r"\bdate\b")
_CP_PATTERNS = (r"d[ée]pense", r"paiement", r"r[ée]alis", r"montant")
_AE_PATTERNS = (r"autorisation", r"engagement", r"\bae\b")

# A group's winning row: the highest period seen so far, with its parsed amounts.
_Winner = tuple[tuple[int, int, str], float | None, float | None]


def _period_key(raw: str | None) -> tuple[int, int, str]:
    """Sortable period key: numeric months compare by value; date-like strings sort lexically.

    Returns ``(is_numeric, value, original)`` so ``max`` prefers the largest numeric month
    (``12`` > ``2`` > ``1``) and falls back to lexicographic order for date-like strings.
    """
    value = (raw or "").strip()
    try:
        return (1, int(float(value.replace(" ", ""))), value)
    except ValueError:
        return (0, 0, value)


def build(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Pure transform: parsed execution rows -> executed budget facts (latest month) + a report."""
    exercice_col = first_column(headers, EXERCICE_PATTERNS)
    mission_col = first_column(headers, MISSION_PATTERNS)
    programme_col = first_column(headers, PROGRAMME_PATTERNS)
    period_col = first_column(headers, _PERIOD_PATTERNS)
    cp_col = first_column(headers, _CP_PATTERNS)
    ae_col = first_column(headers, _AE_PATTERNS)
    if exercice_col is None:
        raise ValueError(f"no exercice column detected in headers {headers!r}")
    if cp_col is None and ae_col is None:
        raise ValueError(f"no dépenses/amount column detected in headers {headers!r}")

    winners: dict[tuple[int, str | None, str | None], _Winner] = {}
    dropped = 0
    for row in rows:
        exercice = parse_year(row.get(exercice_col))
        if exercice is None:
            dropped += 1
            continue
        key = (exercice, clean_cell(row, mission_col), clean_cell(row, programme_col))
        period = _period_key(row.get(period_col)) if period_col else (0, 0, "")
        current = winners.get(key)
        if current is None or period > current[0]:  # keep the latest month only (cumulative YTD)
            ae = parse_amount(row.get(ae_col)) if ae_col else None
            cp = parse_amount(row.get(cp_col)) if cp_col else None
            winners[key] = (period, ae, cp)

    facts = [
        BudgetFact(
            entity_siren=None,
            exercice=exercice,
            mission=mission,
            programme=programme,
            amount_ae_eur=ae,
            amount_cp_eur=cp,
            executed=True,
        )
        for (exercice, mission, programme), (_period, ae, cp) in sorted(
            winners.items(), key=lambda kv: (kv[0][0], kv[0][1] or "", kv[0][2] or "")
        )
    ]
    report = {
        "source_id": SOURCE_ID,
        "rows_in": len(rows),
        "facts_out": len(facts),
        "dropped_no_exercice": dropped,
        "exercices": sorted({f.exercice for f in facts}),
        "executed": True,
    }
    return TransformResult(budget_facts=facts, report=report)


@register_transform(SOURCE_ID)
def transform(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Registered entry point: executed monthly spend -> budget facts (no external dependencies)."""
    return build(headers, rows)
