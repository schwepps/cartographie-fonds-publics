"""Tests for the mission -> tutelle-ministry mapping (FSC-56).

The live Jaune supervises operators by LOLF *mission*, not ministry code. ``load_missions`` parses
the curated map and ``MinistryIndex`` uses it to anchor an operator to its lead ministry — failing
loud on a mission that points at a ministry absent from the reference (golden rule #5: never
mis-resolve a tutelle).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from core.crosswalk import CrosswalkEntry, CrosswalkStatus
from ingestion.crosswalk_io import load_missions
from ingestion.transforms.operateurs_etat import MinistryIndex


def _ministries() -> list[CrosswalkEntry]:
    return [
        CrosswalkEntry(
            denomination="Ministère de l'Enseignement supérieur et de la Recherche",
            status=CrosswalkStatus.reviewed,
            siren="110044013",
            tutelle="MESR",
        ),
        CrosswalkEntry(
            denomination="Ministère de la Culture",
            status=CrosswalkStatus.reviewed,
            siren="110046018",
            tutelle="MC",
        ),
    ]


def test_resolves_a_live_mission_value_to_its_lead_ministry() -> None:
    index = MinistryIndex(
        _ministries(), {"Recherche et enseignement supérieur": "MESR", "Culture": "MC"}
    )
    # The Jaune cell is "Mission\nNNN – Programme"; only the first-line mission drives resolution.
    ministry = index.resolve("Recherche et enseignement supérieur\n150 – Formations supérieures")
    assert ministry is not None
    assert ministry.siren == "110044013"


def test_direct_code_still_wins_over_mission_lookup() -> None:
    index = MinistryIndex(_ministries(), {"Culture": "MC"})
    ministry = index.resolve("MESR")  # code path unaffected
    assert ministry is not None and ministry.siren == "110044013"


def test_unknown_mission_resolves_to_nothing() -> None:
    index = MinistryIndex(_ministries(), {"Culture": "MC"})
    assert index.resolve("Mission Inexistante\n999 – X") is None


def test_mission_pointing_at_absent_ministry_fails_loud() -> None:
    with pytest.raises(ValueError, match="absent from ministry ref"):
        MinistryIndex(_ministries(), {"Défense": "MA"})  # MA not in this reference


def test_missions_colliding_on_normalized_key_fail_loud() -> None:
    # Two distinct labels that normalize to the same key but map to different codes must raise,
    # never silently overwrite (rule #5) — mirroring the ministry-name collision guard.
    with pytest.raises(ValueError, match="mission name collision"):
        MinistryIndex(_ministries(), {"Culture": "MC", "culture": "MESR"})


def test_load_missions_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "missions.yaml"
    path.write_text(
        yaml.safe_dump(
            {"schema_version": 1, "missions": [{"mission": "Culture", "tutelle": "MC"}]}
        ),
        encoding="utf-8",
    )
    assert load_missions(path) == {"Culture": "MC"}


def test_load_missions_fails_loud_on_scalar_row(tmp_path: Path) -> None:
    # A hand-curation slip (a scalar where a mapping is expected) must raise a clear ValueError,
    # not an opaque AttributeError from .get() on a non-dict.
    path = tmp_path / "missions.yaml"
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "missions": ["not-a-mapping"]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="each mission row must be a mapping"):
        load_missions(path)


def test_load_missions_fails_loud_on_duplicate(tmp_path: Path) -> None:
    path = tmp_path / "missions.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "missions": [
                    {"mission": "Culture", "tutelle": "MC"},
                    {"mission": "Culture", "tutelle": "MEF"},
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate mission"):
        load_missions(path)


def test_committed_missions_all_point_at_real_ministries() -> None:
    """The shipped missions.yaml must load cleanly against the shipped ministeres.yaml."""
    # MinistryIndex.load() validates every mission code exists in the ministry reference.
    index = MinistryIndex.load()
    # A spot-check across layers (culture / écologie).
    for value in (
        "Médias, livre et industries culturelles\n334 – Livre",
        "Écologie, développement et mobilité durables\n113 – X",
    ):
        ministry = index.resolve(value)
        assert ministry is not None and ministry.siren is not None
