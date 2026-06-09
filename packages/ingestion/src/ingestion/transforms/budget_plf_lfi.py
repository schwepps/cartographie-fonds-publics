"""Transform PLF/LFI "dépenses selon destination" into voted budget facts (FSC-26).

The PLF/LFI dataset lists voted State spending down the LOLF tree (mission > programme > action >
sous-action) with **autorisations d'engagement (AE)** and **crédits de paiement (CP)**. This
transform produces one :class:`~core.models.BudgetFact` per ``(exercice, mission, programme)`` with
``executed=False`` (voted), summing AE and CP across the finer action/sous-action rows.

**Anti-double-counting (golden rule #8).** We aggregate to the **programme grain** by summing the
finer rows that roll up to it. This assumes the "dépenses selon destination" export ships *leaf*
action/sous-action rows only (no embedded mission/programme subtotal rows) — true of the published
dataset; a source that interleaved subtotals would double-count and must filter them before summing.
The grain is the contract the money-flow layer and the UI methodology note depend on, so it is fixed
here and documented. Missions/programmes are not SIREN entities, so ``entity_siren`` is ``None``
(the fact attaches to the LOLF code, not an org).

Pure: persistence is FSC-35's job. Columns are matched by *pattern* (labels drift across
millésimes), never a frozen header — the same approach the operators transform uses.
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

SOURCE_ID = "budget_plf_lfi"

_AE_PATTERNS = (r"autorisation", r"\bae\b", r"engagement")
_CP_PATTERNS = (r"cr[ée]dit.*paiement", r"paiement", r"\bcp\b")


class _Accumulator:
    """Running AE/CP sums for one (exercice, mission, programme) group; None until a value lands."""

    __slots__ = ("ae", "cp")

    def __init__(self) -> None:
        self.ae: float | None = None
        self.cp: float | None = None

    def add(self, ae: float | None, cp: float | None) -> None:
        if ae is not None:
            self.ae = (self.ae or 0.0) + ae
        if cp is not None:
            self.cp = (self.cp or 0.0) + cp


def build(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Pure transform: parsed PLF rows -> voted budget facts at the programme grain + a report."""
    exercice_col = first_column(headers, EXERCICE_PATTERNS)
    mission_col = first_column(headers, MISSION_PATTERNS)
    programme_col = first_column(headers, PROGRAMME_PATTERNS)
    ae_col = first_column(headers, _AE_PATTERNS)
    cp_col = first_column(headers, _CP_PATTERNS)
    if exercice_col is None:
        raise ValueError(f"no exercice column detected in headers {headers!r}")
    if ae_col is None and cp_col is None:
        raise ValueError(f"no AE/CP amount column detected in headers {headers!r}")

    groups: dict[tuple[int, str | None, str | None], _Accumulator] = {}
    dropped = 0
    for row in rows:
        exercice = parse_year(row.get(exercice_col))
        if exercice is None:  # no usable year -> the row cannot form a fact; surfaced in the report
            dropped += 1
            continue
        mission = clean_cell(row, mission_col)
        programme = clean_cell(row, programme_col)
        ae = parse_amount(row.get(ae_col)) if ae_col else None
        cp = parse_amount(row.get(cp_col)) if cp_col else None
        groups.setdefault((exercice, mission, programme), _Accumulator()).add(ae, cp)

    facts = [
        BudgetFact(
            entity_siren=None,
            exercice=exercice,
            mission=mission,
            programme=programme,
            amount_ae_eur=acc.ae,
            amount_cp_eur=acc.cp,
            executed=False,
        )
        for (exercice, mission, programme), acc in sorted(
            groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "", kv[0][2] or "")
        )
    ]
    report = {
        "source_id": SOURCE_ID,
        "rows_in": len(rows),
        "facts_out": len(facts),
        "dropped_no_exercice": dropped,
        "exercices": sorted({f.exercice for f in facts}),
        "executed": False,
    }
    return TransformResult(budget_facts=facts, report=report)


@register_transform(SOURCE_ID)
def transform(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Registered entry point: voted PLF/LFI credits -> budget facts (no external dependencies)."""
    return build(headers, rows)
