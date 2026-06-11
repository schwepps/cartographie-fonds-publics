"""Transform local public companies (SEM/SPL) → delegated entities + participation edges (FSC-33).

Sociétés d'économie mixte (SEM/SEML) and sociétés publiques locales (SPL/SPLA) are the local end of
the *delegated* layer: companies a collectivité owns a stake in. We identify them from a
SIRENE-derived extract by **catégorie juridique** (the public-sector subset — never a full SIRENE
pull, golden rule #6 in spirit) and emit one ``level=delegated`` entity per company.

**Participation edges record only what is published.** SIRENE alone carries no shareholding, so a
participation edge (public shareholder → company) is emitted **only** when the extract supplies a
resolvable shareholder SIREN; otherwise the company is kept with no edge and **counted** in the
report (golden rule #5 — never invent a link). The edge is structural (ownership): no euro amount.

Pure — persistence is the loader's job. Columns are matched by **pattern** (labels drift); the
catégorie-juridique codes live in one documented table, never frozen in flow logic.
"""

from __future__ import annotations

from core.models import Edge, EdgeType, Entity, Level
from core.resolve import normalize_siren

from ..tabular import first_column
from . import TransformResult, register_transform
from .budget_common import clean_cell

SOURCE_ID = "epl_sem_spl"

# SIRENE catégories juridiques (niveau III) identifying local public companies. Codes are **à
# confirmer** against the INSEE nomenclature during the spike (FSC-33); the filter is driven by this
# table, never frozen elsewhere. Value = the short label carried as the entity's ``category``.
_SEM_SPL_CATEGORIES: dict[str, str] = {
    "5422": "SEM",  # société d'économie mixte (SEM / SEML)
    "5416": "SPL",  # société publique locale (SPL / SPLA)
}

_SIREN_PATTERNS = (r"\bsiren\b", r"siren")
_NAME_PATTERNS = (r"denom", r"raison.?sociale", r"\bnom\b", r"nom")
_CATEGORIE_PATTERNS = (r"cat[ée]gorie.?juridique", r"cat.?jur", r"\bcj\b")
_HOLDER_SIREN_PATTERNS = (
    r"actionnaire.*siren",
    r"siren.*actionnaire",
    r"collectivit[ée].*siren",
)


def build(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Pure transform: SEM/SPL rows → delegated entities + participation edges + a report."""
    siren_col = first_column(headers, _SIREN_PATTERNS)
    categorie_col = first_column(headers, _CATEGORIE_PATTERNS)
    missing = [
        name for name, col in (("siren", siren_col), ("categorie", categorie_col)) if col is None
    ]
    if missing:
        raise ValueError(f"SEM/SPL: required column(s) {missing} not found in headers {headers!r}")
    assert siren_col and categorie_col  # narrowed by the guard
    name_col = first_column(headers, _NAME_PATTERNS)
    holder_col = first_column(headers, _HOLDER_SIREN_PATTERNS)

    entities_by_siren: dict[str, Entity] = {}
    edges_by_key: dict[tuple[str, str], Edge] = {}
    filtered_out_category = 0  # rows outside the SEM/SPL legal-category set
    unresolved_company = 0  # SEM/SPL rows with no usable SIREN (reported, never guessed)
    without_shareholder = 0  # SEM/SPL with no published, resolvable shareholder (no edge invented)

    for row in rows:
        label = _SEM_SPL_CATEGORIES.get(clean_cell(row, categorie_col) or "")
        if label is None:
            filtered_out_category += 1
            continue
        siren = normalize_siren(row.get(siren_col))
        if siren is None:
            unresolved_company += 1
            continue
        entities_by_siren.setdefault(
            siren,
            Entity(
                siren=siren,
                name=clean_cell(row, name_col) or siren,
                level=Level.delegated,
                category=label,
                provenance=SOURCE_ID,
            ),
        )
        holder = normalize_siren(row.get(holder_col)) if holder_col else None
        if holder is None:  # shareholding absent/partial — count, never invent a link (rule #5)
            without_shareholder += 1
            continue
        edges_by_key.setdefault(
            (holder, siren),
            Edge(
                source_siren=holder,  # the public shareholder holds the stake
                target_siren=siren,  # in the SEM/SPL company
                type=EdgeType.participation,
                amount_eur=None,  # structural ownership link; capital share not modelled as euros
                provenance=SOURCE_ID,
            ),
        )

    entities = sorted(entities_by_siren.values(), key=lambda e: e.siren or "")
    edges = sorted(edges_by_key.values(), key=lambda e: (e.source_siren, e.target_siren))
    report = {
        "source_id": SOURCE_ID,
        "rows_in": len(rows),
        "entities_out": len(entities),
        "participation_edges": len(edges),
        "filtered_out_category": filtered_out_category,
        "unresolved_company_siren": unresolved_company,
        "without_shareholder": without_shareholder,
        "categories": sorted({e.category for e in entities if e.category}),
    }
    return TransformResult(entities=entities, edges=edges, report=report)


@register_transform(SOURCE_ID)
def transform(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Registered entry point: SEM/SPL rows → delegated entities + participation edges."""
    return build(headers, rows)
