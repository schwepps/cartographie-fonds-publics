"""Transform DECP (*données essentielles de la commande publique*) into contracts + delegates edges.

FSC-31 (contracts) + FSC-39 (delegates edges). Consumes the **consolidated tabular** DECP extract
(``decp_commande_publique``, ``platform: datagouv_api``) — the daily-rebuilt, all-millésimes file
whose columns are documented at data.gouv.fr. This transform:

1. **Collapses each market to its current attribution.** A market (keyed by ``uid``) is spread over
   several rows: one per co-titulaire and one per amendment (``modification_id``). We keep the rows
   flagged ``donneesActuelles`` (else the highest ``modification_id``), so an amended ``montant`` is
   counted once at its current value — never summed across amendments.
2. **Splits ``montant`` equally among a market's co-titulaires.** The DECP ``montant`` is the global
   market amount, repeated on every co-titulaire row. Splitting before building each
   :class:`~core.models.Contract` is the anti-double-counting convention (golden rule #8); summing
   the shares back up in ``aggregate_delegates_edges`` reproduces the market total exactly.
3. **Resolves parties to SIREN.** ``acheteur_id`` / ``titulaire_id`` carry SIRET (14 digits) as
   often as SIREN (9); ``siren_from_identifier`` reduces SIRET→SIREN. A party with no usable id
   falls back to a reviewed-crosswalk lookup by name; the still-unresolved are **counted and listed
   in the report** (the crosswalk backlog), never dropped, never guessed (golden rule #5).
4. **Builds the graph slice via the shared core helper** (``core.contracts``): aggregated
   ``delegates`` edges (acheteur → titulaire) + ``level=delegated`` titulaire entities. Buyer
   entities are intentionally not emitted (owned by other layers; see ``core.contracts``).

Headers drift, so columns are matched by **pattern**, never frozen positions (mirrors
``operateurs_etat``). It is pure; persistence is the loader's job (``ingestion.load``).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from core.contracts import DECP_PROVENANCE, aggregate_delegates_edges, delegated_entities
from core.crosswalk import Crosswalk
from core.models import Contract, Nature
from core.resolve import normalize_name, siren_from_identifier

from ..crosswalk_io import load_crosswalk
from ..tabular import first_column
from . import TransformResult, register_transform

SOURCE_ID = DECP_PROVENANCE

# Column detection (consolidated-tabular labels; match by pattern, never a frozen header).
# Exact `*_nom`/`*_id` first — the consolidated file also has acheteur_commune_nom /
# titulaire_region_nom etc., so a broad `*nom` pattern would grab a geography column before the
# party name. `titulaire_?id` does not match `titulaire_typeIdentifiant` (no "id" after the prefix).
_ACHETEUR_ID_PATTERNS = (r"^acheteur_?id$", r"acheteur_?id", r"acheteur.*sire[nt]")
_ACHETEUR_NAME_PATTERNS = (r"^acheteur_nom$", r"acheteur.*(denom|raison)")
_TITULAIRE_ID_PATTERNS = (r"^titulaire_?id$", r"titulaire_?id", r"titulaire.*sire[nt]")
_TITULAIRE_NAME_PATTERNS = (r"^titulaire_nom$", r"titulaire.*(denom|raison)")
_MONTANT_PATTERNS = (r"^montant$", r"montant")
_NATURE_PATTERNS = (r"nature",)
_DATE_PATTERNS = (r"date.*notif", r"exercice", r"ann[eé]e")
_UID_PATTERNS = (r"^uid$", r"\buid\b")
# The internal market id, shared across a market's co-titulaire and amendment rows (anchored so it
# never matches acheteur_id / titulaire_id / idAccordCadre). With acheteur_id it keys a market when
# `uid` is absent.
_MARKET_ID_PATTERNS = (r"^id$",)
_MODIFICATION_PATTERNS = (r"modification",)
_CURRENT_PATTERNS = (r"donnees?.*actuel", r"donnee.*actuel")

_YEAR_RE = re.compile(r"(20\d{2})")
_TRUE = {"true", "1", "oui", "vrai", "t", "yes"}


@dataclass(frozen=True)
class _Columns:
    acheteur_id: str
    titulaire_id: str
    montant: str
    nature: str
    acheteur_name: str | None
    titulaire_name: str | None
    date: str | None
    uid: str | None
    market_id: str | None
    modification: str | None
    current: str | None


def _detect_columns(headers: list[str]) -> _Columns:
    """Locate the columns the transform needs; the four load-bearing ones fail loud if missing.

    Required: acheteur_id, titulaire_id, montant, nature. The rest are optional refinements.
    """
    acheteur_id = first_column(headers, _ACHETEUR_ID_PATTERNS)
    titulaire_id = first_column(headers, _TITULAIRE_ID_PATTERNS)
    montant = first_column(headers, _MONTANT_PATTERNS)
    nature = first_column(headers, _NATURE_PATTERNS)
    missing = [
        name
        for name, col in (
            ("acheteur_id", acheteur_id),
            ("titulaire_id", titulaire_id),
            ("montant", montant),
            ("nature", nature),
        )
        if col is None
    ]
    if missing:
        raise ValueError(f"DECP: required column(s) {missing} not found in headers {headers!r}")
    assert acheteur_id and titulaire_id and montant and nature  # narrowed by the guard above
    return _Columns(
        acheteur_id=acheteur_id,
        titulaire_id=titulaire_id,
        montant=montant,
        nature=nature,
        acheteur_name=first_column(headers, _ACHETEUR_NAME_PATTERNS),
        titulaire_name=first_column(headers, _TITULAIRE_NAME_PATTERNS),
        date=first_column(headers, _DATE_PATTERNS),
        uid=first_column(headers, _UID_PATTERNS),
        market_id=first_column(headers, _MARKET_ID_PATTERNS),
        modification=first_column(headers, _MODIFICATION_PATTERNS),
        current=first_column(headers, _CURRENT_PATTERNS),
    )


def _parse_amount(value: str) -> float | None:
    """Parse a DECP montant (plain, US- or French-formatted) to float; blank/garbage → None.

    The decimal separator is the RIGHTMOST of ``,`` / ``.`` — so ``1.234,56`` (French) and
    ``1,234.56`` (US) both yield 1234.56, and the other separator is dropped as a thousands group.
    """
    cleaned = re.sub(r"[^\d,.\-]", "", str(value or ""))
    if not cleaned:
        return None
    if cleaned.rfind(",") > cleaned.rfind("."):
        cleaned = cleaned.replace(".", "").replace(",", ".")  # French: ',' decimal, '.' thousands
    else:
        cleaned = cleaned.replace(",", "")  # US/plain: '.' decimal, ',' thousands
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_nature(value: str) -> Nature | None:
    """Map a DECP nature label to the domain enum (concession vs marché); unknown → None."""
    text = str(value or "").strip().lower()
    if not text:
        return None
    if "concession" in text:
        return Nature.concession
    if "march" in text:  # "marché", "marche", "marché de partenariat"…
        return Nature.marche
    return None


def _parse_year(value: str | None) -> int | None:
    match = _YEAR_RE.search(str(value or ""))
    return int(match.group(1)) if match else None


def _market_key(row: dict[str, str], cols: _Columns) -> str:
    """A stable market id shared across a market's co-titulaire and amendment rows.

    Prefer ``uid``; else ``acheteur_id + id`` (the internal market id, also shared across those
    rows). Only as a last resort — no uid and no id column — fall back to ``acheteur_id +
    titulaire_id``, which cannot group co-titulaires (each becomes its own "market"); real DECP
    always carries both uid and id, so this degraded path is for an unexpected format only.
    """
    if cols.uid:
        uid = (row.get(cols.uid) or "").strip()
        if uid:
            return uid
    acheteur = (row.get(cols.acheteur_id) or "").strip()
    if cols.market_id:
        market_id = (row.get(cols.market_id) or "").strip()
        if market_id:
            return f"{acheteur}::{market_id}"
    return f"{acheteur}::{(row.get(cols.titulaire_id) or '').strip()}"


def _current_rows(rows: list[dict[str, str]], cols: _Columns) -> list[dict[str, str]]:
    """Keep a market's current attribution: ``donneesActuelles`` rows, else the latest amendment."""
    if cols.current:
        current = [r for r in rows if str(r.get(cols.current) or "").strip().lower() in _TRUE]
        if current:
            return current
    if cols.modification:
        mods = [(_int_or_zero(r.get(cols.modification)), r) for r in rows]
        latest = max(m for m, _ in mods)
        return [r for m, r in mods if m == latest]
    return rows


def _int_or_zero(value: str | None) -> int:
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else 0


def _split_amount(amount: float | None, n: int) -> list[float | None]:
    """Split ``amount`` into ``n`` shares that sum back to it **exactly to the cent**.

    Works in integer cents and hands the rounding remainder to the first few shares (so 100 / 3 →
    33.34 + 33.33 + 33.33 = 100.00, not 33.333… ×3 which would drift in float). This keeps the
    anti-double-counting guarantee (summing a market's delegates edges reproduces its montant) exact
    rather than approximate. ``None`` amount → ``None`` shares.
    """
    if amount is None:
        return [None] * n
    total_cents = round(amount * 100)
    base, remainder = divmod(total_cents, n)
    return [(base + (1 if i < remainder else 0)) / 100 for i in range(n)]


def build(
    headers: list[str], rows: list[dict[str, str]], *, crosswalk: Crosswalk
) -> TransformResult:
    """Pure transform: DECP consolidated-tabular rows → contracts + delegates edges + report."""
    cols = _detect_columns(headers)

    markets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        markets[_market_key(row, cols)].append(row)

    contracts: list[Contract] = []
    titulaire_names: dict[str, str] = {}
    # Resolution accounting at the party-end level (golden rule #5: report the match rate).
    ends_total = 0
    ends_resolved = 0
    unresolved_names: set[str] = set()

    def resolve_party(identifier: str, name: str) -> str | None:
        nonlocal ends_total, ends_resolved
        ends_total += 1
        siren = siren_from_identifier(identifier)
        if siren is None:  # no usable id → reviewed-crosswalk fallback by name (never guessed)
            siren = crosswalk.resolve(normalize_name(name))
        if siren is None:
            if name.strip():
                unresolved_names.add(name.strip())
            return None
        ends_resolved += 1
        return siren

    for _uid, market_rows in markets.items():
        current = _current_rows(market_rows, cols)
        # Distinct co-titulaires of the current attribution: dedupe repeated titulaire ids, but keep
        # BLANK-id rows distinct (two unnamed co-titulaires are two parties, not one). Sort by id so
        # the remainder cent of the equal split always lands on the same titulaire regardless of the
        # upstream row order (deterministic per-supplier amounts across rebuilds).
        seen_titulaire_ids: set[str] = set()
        titulaire_rows: list[dict[str, str]] = []
        for row in current:
            tid = (row.get(cols.titulaire_id) or "").strip()
            if tid and tid in seen_titulaire_ids:
                continue
            if tid:
                seen_titulaire_ids.add(tid)
            titulaire_rows.append(row)
        titulaire_rows.sort(key=lambda r: (r.get(cols.titulaire_id) or "").strip())
        n_titulaires = len(titulaire_rows) or 1
        first = current[0]
        montant = _parse_amount(first.get(cols.montant, ""))
        # Equal split among co-titulaires, remainder-distributed so the shares sum back exactly.
        shares = _split_amount(montant, n_titulaires)
        nature = _parse_nature(first.get(cols.nature, ""))
        exercice = _parse_year(first.get(cols.date)) if cols.date else None
        acheteur_name = first.get(cols.acheteur_name, "") if cols.acheteur_name else ""
        acheteur_siren = resolve_party(first.get(cols.acheteur_id, ""), acheteur_name)

        for share, row in zip(shares, titulaire_rows, strict=True):
            titulaire_name = row.get(cols.titulaire_name, "") if cols.titulaire_name else ""
            titulaire_siren = resolve_party(row.get(cols.titulaire_id, ""), titulaire_name)
            if titulaire_siren is not None and titulaire_name.strip():
                titulaire_names[titulaire_siren] = titulaire_name.strip()
            contracts.append(
                Contract(
                    acheteur_siren=acheteur_siren,
                    titulaire_siren=titulaire_siren,
                    montant_eur=share,
                    nature=nature,
                    exercice=exercice,
                    provenance=SOURCE_ID,
                )
            )

    edges = aggregate_delegates_edges(contracts, provenance=SOURCE_ID)
    entities = delegated_entities(contracts, names=titulaire_names, provenance=SOURCE_ID)

    report = {
        "source_id": SOURCE_ID,
        "markets": len(markets),
        "contracts": len(contracts),
        "delegates_edges": len(edges),
        "delegated_entities": len(entities),
        "parties_total": ends_total,
        "parties_resolved": ends_resolved,
        "resolution_rate": (ends_resolved / ends_total) if ends_total else 0.0,
        "unresolved": len(unresolved_names),
        "unresolved_parties": sorted(unresolved_names),
    }
    return TransformResult(entities=entities, edges=edges, contracts=contracts, report=report)


@register_transform(SOURCE_ID)
def transform(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Registered entry point: resolve unresolved parties against the committed crosswalk."""
    return build(headers, rows, crosswalk=load_crosswalk())
