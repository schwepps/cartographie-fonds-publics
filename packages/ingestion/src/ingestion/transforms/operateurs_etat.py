"""Transform the *Jaune opérateurs de l'État* into entities + tutelle edges (FSC-25).

The Jaune lists ~430 State operators with a category and a supervising-ministry (*tutelle*) but
**no SIREN**. This transform:

1. builds an :class:`Entity` per operator (``level=state``, with its category),
2. resolves each operator's SIREN through the reviewed crosswalk (``core.resolution`` — exact,
   never guessed; unresolved operators are kept with ``siren=None`` and surfaced in the report,
   never dropped, per golden rule #5),
3. resolves each operator's tutelle to a ministry via the curated ministry reference, emits the
   ministry as an :class:`Entity` and a ``tutelle`` :class:`Edge` (ministry -> operator) **only when
   both ends carry a SIREN** (``Edge`` requires one on each side).

It is pure: persistence to Supabase is FSC-35's job. The registered entry point loads the committed
crosswalk + ministry reference; :func:`build` takes them as arguments for injectable, offline tests.
"""

from __future__ import annotations

from pathlib import Path

from core.crosswalk import Crosswalk, CrosswalkEntry
from core.models import Edge, EdgeType, Entity, Level
from core.resolution import resolve_entities
from core.resolve import normalize_name

from ..crosswalk_io import load_crosswalk, load_ministries, load_missions
from ..tabular import first_column
from . import TransformResult, register_transform

SOURCE_ID = "operateurs_etat"
MINISTRY_CATEGORY = "ministère"

# Column detection (the Jaune's labels drift; match by pattern, never a frozen header). The operator
# name is coalesce(leaf "Opérateur de la catégorie", grouping "Opérateur ou catégorie d'opérateurs")
# — either column alone drops ~165 of 431 rows (measured by the FSC-48 spike).
_NAME_PATTERNS = (r"op[eé]rateur de la cat", r"d[eé]nomination", r"raison.?sociale", r"\bnom\b")
_NAME_FALLBACK_PATTERNS = (r"op[eé]rateur ou", r"cat[eé]gorie d['’ ]?op", r"op[eé]rateur")
_TUTELLE_PATTERNS = (r"tutelle", r"minist", r"mission.*programme")
_CATEGORY_PATTERNS = (r"cat[eé]gorie\s+juridique", r"cat[eé]gorie", r"nature")


class MinistryIndex:
    """Resolve an operator's tutelle value (a ministry code, name, *or* LOLF mission) to its entry.

    Indexed by code (case-insensitive, the primary key operators reference) with a normalized-name
    fallback, so resolution survives whether the live Jaune emits ``MESR`` or the full label. The
    live Jaune actually supervises by **mission** (``"Recherche et enseignement supérieur\\n150 –
    …"``), so an optional mission map (``mission label -> ministry code``, from ``missions.yaml``)
    lets the same lookup anchor those operators to their lead ministry (FSC-56).
    """

    def __init__(
        self, entries: list[CrosswalkEntry], missions: dict[str, str] | None = None
    ) -> None:
        # Codes are already unique (load_ministries guards). The name-fallback index must guard its
        # own collisions too: two ministries sharing a normalized name must never silently resolve
        # to one SIREN (golden rule #5), mirroring Crosswalk.from_entries / load_ministries.
        self._by_code = {(e.tutelle or "").strip().upper(): e for e in entries}
        self._by_name: dict[str, CrosswalkEntry] = {}
        for entry in entries:
            existing = self._by_name.get(entry.normalized_name)
            if existing is not None and existing.siren != entry.siren:
                raise ValueError(
                    f"ministry name collision on key {entry.normalized_name!r}: "
                    f"{existing.denomination!r} ({existing.siren}) vs "
                    f"{entry.denomination!r} ({entry.siren})"
                )
            self._by_name.setdefault(entry.normalized_name, entry)
        # mission label (normalized) -> ministry code. Fail loud if a mission points at a code with
        # no ministry entry, or if two distinct mission labels collide on the same normalized key
        # with different codes: the map and the reference must never silently disagree (rule #5),
        # mirroring the ministry-name collision guard above.
        self._by_mission: dict[str, str] = {}
        for mission, code in (missions or {}).items():
            code_up = code.strip().upper()
            if code_up not in self._by_code:
                raise ValueError(
                    f"mission {mission!r} maps to ministry code {code!r} absent from ministry ref"
                )
            key = normalize_name(mission)
            existing_code = self._by_mission.get(key)
            if existing_code is not None and existing_code != code_up:
                raise ValueError(
                    f"mission name collision on key {key!r}: maps to both "
                    f"{existing_code!r} and {code_up!r}"
                )
            self._by_mission[key] = code_up

    @classmethod
    def load(
        cls, path: Path | str | None = None, missions_path: Path | str | None = None
    ) -> MinistryIndex:
        """Load the reviewed ministry reference (+ the committed mission map when ``path`` is None).

        Passing a custom ``path`` (offline tests) loads no mission map unless ``missions_path`` is
        given too, so a fixture ministry reference stays isolated from the committed missions.
        """
        entries = load_ministries() if path is None else load_ministries(path)
        if missions_path is not None:
            missions = load_missions(missions_path)
        elif path is None:
            missions = load_missions()
        else:
            missions = {}
        return cls(entries, missions)

    def resolve(self, tutelle_value: str | None) -> CrosswalkEntry | None:
        value = (tutelle_value or "").strip()
        if not value:
            return None
        direct = self._by_code.get(value.upper()) or self._by_name.get(normalize_name(value))
        if direct is not None:
            return direct
        # Fall back to the LOLF mission on the first line ("Mission\nNNN – Programme" in the Jaune).
        mission = value.splitlines()[0].strip()
        code = self._by_mission.get(normalize_name(mission))
        return self._by_code.get(code) if code else None


def _coalesce(row: dict[str, str], cols: list[str]) -> str:
    """First non-empty value across ``cols`` in priority order — the operator's name."""
    for col in cols:
        value = str(row.get(col) or "").strip()
        if value:
            return value
    return ""


def _detect_columns(headers: list[str]) -> tuple[list[str], str | None, str | None]:
    """Locate the operator-name column(s), the category column, and the tutelle column."""
    leaf = first_column(headers, _NAME_PATTERNS)
    grouping = first_column(headers, _NAME_FALLBACK_PATTERNS)
    name_cols = list(dict.fromkeys(c for c in (leaf, grouping) if c))  # ordered, de-duplicated
    if not name_cols:
        raise ValueError(f"no operator-name column detected in headers {headers!r}")
    tutelle_col = first_column(headers, _TUTELLE_PATTERNS)
    # Category must not collide with a name column (the grouping label also contains "catégorie").
    category_col = next(
        (
            first_column([h], _CATEGORY_PATTERNS)
            for h in headers
            if h not in name_cols and first_column([h], _CATEGORY_PATTERNS)
        ),
        None,
    )
    return name_cols, category_col, tutelle_col


def build(
    headers: list[str],
    rows: list[dict[str, str]],
    *,
    crosswalk: Crosswalk,
    ministries: MinistryIndex,
) -> TransformResult:
    """Pure transform: parsed Jaune rows -> ministry + operator entities, tutelle edges, report."""
    name_cols, category_col, tutelle_col = _detect_columns(headers)

    # One operator Entity per distinct name (the normalized name is the resolution key). The Jaune
    # repeats an operator across missions; de-duplicating here keeps one entity (the entities table
    # has a unique SIREN) and one tutelle edge. Blank/empty-normalizing rows are skipped, not lost.
    operators_by_key: dict[str, Entity] = {}
    tutelle_by_key: dict[str, str] = {}
    for row in rows:
        denomination = _coalesce(row, name_cols)
        key = normalize_name(denomination)
        if not key or key in operators_by_key:
            continue
        category = str(row.get(category_col) or "").strip() if category_col else None
        operators_by_key[key] = Entity(
            name=denomination,
            siren=None,
            level=Level.state,
            category=category or None,
            provenance=SOURCE_ID,
        )
        if tutelle_col:
            tutelle_by_key[key] = str(row.get(tutelle_col) or "").strip()
    operators = list(operators_by_key.values())

    # Resolve SIRENs through the crosswalk — the canonical report (rate + unresolved backlog).
    result = resolve_entities(operators, crosswalk)
    siren_by_key = {normalize_name(e.name): e.siren for e in result.resolved}

    entities: list[Entity] = []
    edges: list[Edge] = []
    ministries_seen: dict[str, Entity] = {}  # by SIREN, de-duplicated
    edges_seen: set[tuple[str, str]] = set()
    tutelle_resolved = 0

    for operator in operators:
        key = normalize_name(operator.name)
        siren = siren_by_key.get(key)  # None when unresolved — entity kept, never dropped
        ministry = ministries.resolve(tutelle_by_key.get(key))
        parent_siren = ministry.siren if ministry else None
        entities.append(operator.model_copy(update={"siren": siren, "parent_siren": parent_siren}))
        if ministry is not None and ministry.siren is not None:
            tutelle_resolved += 1
            ministries_seen.setdefault(
                ministry.siren,
                Entity(
                    name=ministry.denomination,
                    siren=ministry.siren,
                    level=Level.state,
                    category=MINISTRY_CATEGORY,
                    provenance=SOURCE_ID,
                ),
            )
            # A tutelle edge needs a SIREN on both ends (Edge.*_siren is required).
            if siren is not None and (ministry.siren, siren) not in edges_seen:
                edges_seen.add((ministry.siren, siren))
                edges.append(
                    Edge(
                        source_siren=ministry.siren,
                        target_siren=siren,
                        type=EdgeType.tutelle,
                        provenance=SOURCE_ID,
                    )
                )

    # Ministries first (graph roots), then operators — both deterministically ordered.
    ordered_ministries = sorted(ministries_seen.values(), key=lambda e: e.siren or "")
    ordered_operators = sorted(entities, key=lambda e: normalize_name(e.name))
    report = result.to_report_dict()
    report.update(
        {
            "source_id": SOURCE_ID,
            "operators": len(operators),
            "ministries": len(ordered_ministries),
            "tutelle_edges": len(edges),
            "operators_with_tutelle": tutelle_resolved,
        }
    )
    return TransformResult(
        entities=ordered_ministries + ordered_operators, edges=edges, report=report
    )


@register_transform(SOURCE_ID)
def transform(headers: list[str], rows: list[dict[str, str]]) -> TransformResult:
    """Registered entry point: resolve against the committed crosswalk + ministry reference."""
    return build(headers, rows, crosswalk=load_crosswalk(), ministries=MinistryIndex.load())
