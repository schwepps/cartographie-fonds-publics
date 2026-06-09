"""Scalar parsing + cell access shared by the two State-budget transforms (PLF/LFI + execution).

Both budget sources arrive as French open-data CSV (snapshotted ``all_varchar``): amounts carry
thousands separators (space / NBSP) and a decimal comma, years/months are numeric-ish text. These
helpers coerce that faithfully — **preserving ``0``** (a real budget value, golden rule on falsy
safety) and mapping only genuinely-empty/non-numeric cells to ``None``. Column *detection* differs
per source (PLF has AE+CP by action; execution has monthly dépenses), so it stays in each module;
the source-agnostic coercion + cell access is shared here.
"""

from __future__ import annotations

import math
import re

# Mission/programme are stored as their LOLF *codes* (registry join_keys: code_mission /
# code_programme), falling back to the label column when a source ships no code. Codes come first.
MISSION_PATTERNS = (r"code.?mission", r"mission")
PROGRAMME_PATTERNS = (r"code.?programme", r"programme")
EXERCICE_PATTERNS = (r"exercice", r"ann[ée]e", r"\byear\b")

_BLANK_TOKENS = frozenset({"", "nan", "na", "n/a", "null", "none", "-"})
# Strip every whitespace separator (\s matches NBSP U+00A0 and narrow NBSP U+202F too) plus the €.
_STRIP_RE = re.compile(r"[\s€]")


def parse_amount(raw: str | None) -> float | None:
    """Coerce a French money cell to euros. Blank/non-numeric/non-finite -> None; ``0`` preserved.

    Handles thousands separators (ASCII space, NBSP, narrow NBSP) and a decimal comma, e.g.
    ``"1 800 000,50"`` -> ``1800000.5``. ``"0"`` -> ``0.0`` (never None). ``inf``/``nan`` are
    rejected so a garbled cell can't silently poison an aggregate (golden rule #5/#8).
    """
    if raw is None:
        return None
    s = _STRIP_RE.sub("", raw)
    if s.lower() in _BLANK_TOKENS:
        return None
    if "," in s and "." in s:  # '.' thousands, ',' decimal (e.g. "1.800.000,50")
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        value = float(s)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def parse_year(raw: str | None) -> int | None:
    """Coerce an exercice cell to a 4-digit year int, else None (the row can't form a fact)."""
    if raw is None:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", raw)
    return int(match.group()) if match else None


def clean_cell(row: dict[str, str], col: str | None) -> str | None:
    """A trimmed cell value, or None when the column is absent or the value is blank."""
    if col is None:
        return None
    value = str(row.get(col) or "").strip()
    return value or None
