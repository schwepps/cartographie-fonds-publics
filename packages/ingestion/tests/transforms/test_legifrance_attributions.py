"""Offline transform tests for ministerial attributions (FSC-27, manual-first).

Drives ``build`` against constructed editorial entries + the sample ministry reference, asserting
the golden-rule-#5 contract: an entry resolves to its ministry SIREN through the reference (code or
denomination) or is reported as unresolved — never guessed. Also pins that the committed editorial
file parses, every reference is an http(s) URL, and the demo set resolves fully.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ingestion.transforms.legifrance_attributions import (
    SOURCE_ID,
    AttributionEntry,
    build,
    load_attribution_entries,
    transform,
)
from ingestion.transforms.operateurs_etat import MinistryIndex

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _ministries() -> MinistryIndex:
    # Sample reference: code AA -> 900000017 ("Ministère Alpha"), GG -> 900000025.
    return MinistryIndex.load(FIXTURES / "ministeres_sample.yaml")


def test_build_resolves_siren_by_code_and_stamps_provenance() -> None:
    entries = [
        AttributionEntry(
            legal_ref="Décret n° 2025-1021 du 29 octobre 2025",
            source_url="https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052457282",
            txt="Compétence Alpha",
            tutelle="AA",
        )
    ]
    result = build(entries, ministries=_ministries())
    assert len(result.attributions) == 1
    a = result.attributions[0]
    assert a.entity_siren == "900000017"  # resolved via the ministry code
    assert (a.legal_ref or "").startswith("Décret n° 2025-1021")
    assert (a.source_url or "").startswith("https://")
    assert a.provenance == SOURCE_ID
    assert result.report == {
        "source_id": SOURCE_ID,
        "total": 1,
        "attributions": 1,
        "unresolved": 0,
        "unresolved_entries": [],
    }


def test_build_resolves_by_denomination_when_no_code() -> None:
    entries = [
        AttributionEntry(
            legal_ref="Décret X",
            source_url="https://www.legifrance.gouv.fr/x",
            txt="",
            denomination="Ministère Alpha",
        )
    ]
    result = build(entries, ministries=_ministries())
    assert result.attributions[0].entity_siren == "900000017"


def test_build_routes_unresolved_to_report_never_guesses() -> None:
    entries = [
        AttributionEntry(
            legal_ref="Décret Z", source_url="https://x.gouv.fr", txt="", tutelle="ZZZ"
        )
    ]
    result = build(entries, ministries=_ministries())
    assert result.attributions == []  # never attached to a guessed SIREN
    assert result.report["unresolved"] == 1
    assert result.report["unresolved_entries"][0]["tutelle"] == "ZZZ"


def test_committed_editorial_file_parses_and_resolves_fully() -> None:
    # The shipped demo set must be real (http(s) refs) and resolve against the committed reference.
    entries = load_attribution_entries()
    assert len(entries) >= 3
    assert all(e.source_url.startswith("https://www.legifrance.gouv.fr") for e in entries)
    result = transform([], [])  # registered entry point: committed file + real ministry reference
    assert result.report["unresolved"] == 0
    assert len(result.attributions) == len(entries)
    assert all(a.provenance == SOURCE_ID for a in result.attributions)


def test_loader_rejects_non_http_url(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema_version: 1\nentries:\n  - tutelle: MESR\n    legal_ref: D\n"
        "    source_url: ftp://x\n    txt: t\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="http"):
        load_attribution_entries(bad)


def test_loader_rejects_bad_schema_version(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 99\nentries: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_attribution_entries(bad)


def test_loader_rejects_entry_without_target(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema_version: 1\nentries:\n  - legal_ref: D\n    source_url: https://x\n    txt: t\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="tutelle.*denomination|denomination"):
        load_attribution_entries(bad)
