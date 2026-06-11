"""Entity resolution. SIREN-first, then reviewed crosswalk for hard cases."""

from __future__ import annotations

import re
import unicodedata

_DIGITS = re.compile(r"\D")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Articles/conjunctions + bare legal-form tokens dropped before name comparison. Removing them
# lets "Établissement public X" / "EP X" collapse to the same key while keeping the substantive
# name. Conservative by design: over-stripping can only DEMOTE a would-be unique match to the
# ambiguous (crosswalk) tier — it never fabricates an accepted SIREN, because auto-acceptance
# still requires *exact* equality of two normalized keys (see the resolver spike).
_LEGAL_FORMS: frozenset[str] = frozenset(
    {
        "de",
        "du",
        "des",
        "la",
        "le",
        "les",
        "l",
        "d",
        "et",
        "en",
        "au",
        "aux",
        "a",
        "etablissement",
        "public",
        "publics",
        "epic",
        "epa",
        "epst",
        "gip",
        "sa",
        "sas",
        "sarl",
    }
)


def normalize_siren(value: str | None) -> str | None:
    """Return a 9-digit SIREN or None. Never guess."""
    if not value:
        return None
    digits = _DIGITS.sub("", str(value))
    return digits if len(digits) == 9 else None


def siren_from_identifier(value: str | None) -> str | None:
    """Return a 9-digit SIREN from a SIREN *or* a 14-digit SIRET identifier, else None.

    DECP identifies acheteurs/titulaires by SIRET (14 digits — the establishment) at least as often
    as by SIREN (9 digits — the legal unit). A SIRET's first 9 digits *are* its SIREN, so we reduce
    it to the canonical join key. Anything that is neither a clean 9- nor 14-digit number (foreign,
    malformed, missing) returns None — never guessed (golden rule #5: the unresolved go to the
    crosswalk/report, never a fabricated key).
    """
    if not value:
        return None
    digits = _DIGITS.sub("", str(value))
    if len(digits) == 14:
        digits = digits[:9]
    return digits if len(digits) == 9 else None


def normalize_name(value: str | None) -> str:
    """Return a comparison key for an entity name: accent-folded, lowercased, and stripped of
    articles + bare legal-form tokens. None/empty -> "".

    This is a *key builder*, not a matcher: the resolver treats only exact equality of two keys
    as a hit (golden rule #5 — never guess). Two names that disagree after normalization are
    routed to the reviewed crosswalk, never auto-joined.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    tokens = [t for t in _NON_ALNUM.split(ascii_only.casefold()) if t and t not in _LEGAL_FORMS]
    return " ".join(tokens)


def match_rate(left_sirens: set[str], right_sirens: set[str]) -> float:
    """Share of left entities that have a counterpart on the right (by SIREN)."""
    if not left_sirens:
        return 0.0
    return len(left_sirens & right_sirens) / len(left_sirens)
