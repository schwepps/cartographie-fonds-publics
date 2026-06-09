"""Crosswalk engine: accepted rows resolve, backlog rows don't, and invariants fail loud."""

from __future__ import annotations

from typing import Any

import pytest
from core.crosswalk import Crosswalk, CrosswalkEntry, CrosswalkStatus
from core.resolve import normalize_name
from pydantic import ValidationError


def _entry(denomination: str, status: str, siren: str | None = None, **kw: Any) -> CrosswalkEntry:
    return CrosswalkEntry(
        denomination=denomination, status=CrosswalkStatus(status), siren=siren, **kw
    )


@pytest.mark.parametrize("status", ["auto", "reviewed"])
def test_accepted_rows_resolve_to_their_siren(status: str) -> None:
    cw = Crosswalk.from_entries([_entry("Centre national X", status, "180089013")])
    assert cw.resolve(normalize_name("Centre national X")) == "180089013"


@pytest.mark.parametrize("status", ["pending", "category"])
def test_backlog_rows_never_resolve(status: str) -> None:
    cw = Crosswalk.from_entries(
        [_entry("Universités et assimilés", status, candidate_sirens=["111222333"])]
    )
    assert normalize_name("Universités et assimilés") in cw  # present, but not resolvable
    assert cw.resolve(normalize_name("Universités et assimilés")) is None


def test_unknown_name_resolves_to_none() -> None:
    cw = Crosswalk.from_entries([_entry("Known", "auto", "180089013")])
    assert cw.resolve(normalize_name("Totally unknown")) is None


def test_normalized_name_is_derived_from_denomination() -> None:
    # A bogus normalized_name in the input is ignored: the denomination is the source of truth.
    entry = CrosswalkEntry(
        denomination="Établissement public du Louvre",
        status=CrosswalkStatus.auto,
        siren="180089013",
        normalized_name="garbage",
    )
    assert entry.normalized_name == normalize_name("Établissement public du Louvre")


def test_duplicate_key_same_siren_is_idempotent() -> None:
    cw = Crosswalk.from_entries(
        [
            _entry("Centre national X", "auto", "180089013"),
            _entry("Centre National  X", "reviewed", "180089013"),
        ]
    )
    assert len(cw) == 1
    assert cw.resolve(normalize_name("Centre national X")) == "180089013"


def test_duplicate_key_conflicting_siren_fails_loud() -> None:
    with pytest.raises(ValueError, match="conflicting SIRENs"):
        Crosswalk.from_entries(
            [
                _entry("École Normale", "reviewed", "180089013"),
                _entry("École normale", "reviewed", "775685019"),
            ]
        )


def test_malformed_siren_on_accepted_row_raises() -> None:
    with pytest.raises(ValidationError):
        _entry("Bad SIREN", "reviewed", "not-a-siren")


def test_accepted_row_without_siren_raises() -> None:
    with pytest.raises(ValidationError, match="must carry a SIREN"):
        _entry("Missing SIREN", "auto", None)


def test_backlog_row_with_siren_raises() -> None:
    with pytest.raises(ValidationError, match="must not carry a SIREN"):
        _entry("Premature", "pending", "180089013")


def test_blank_denomination_raises() -> None:
    with pytest.raises(ValidationError, match="non-empty denomination"):
        _entry("   ", "pending")


def test_entries_are_sorted_for_stable_output() -> None:
    cw = Crosswalk.from_entries(
        [_entry("Zebra", "pending"), _entry("Alpha", "pending"), _entry("Mike", "pending")]
    )
    keys = [e.normalized_name for e in cw.entries()]
    assert keys == sorted(keys)


def test_unknown_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        CrosswalkEntry(denomination="X", status=CrosswalkStatus.pending, bogus="nope")  # type: ignore[call-arg]
