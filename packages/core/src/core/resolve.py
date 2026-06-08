"""Entity resolution. SIREN-first, then reviewed crosswalk for hard cases."""

from __future__ import annotations

import re

_DIGITS = re.compile(r"\D")


def normalize_siren(value: str | None) -> str | None:
    """Return a 9-digit SIREN or None. Never guess."""
    if not value:
        return None
    digits = _DIGITS.sub("", str(value))
    return digits if len(digits) == 9 else None


def match_rate(left_sirens: set[str], right_sirens: set[str]) -> float:
    """Share of left entities that have a counterpart on the right (by SIREN)."""
    if not left_sirens:
        return 0.0
    return len(left_sirens & right_sirens) / len(left_sirens)
