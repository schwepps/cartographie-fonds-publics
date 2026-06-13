"""Offline transform tests for Cour des comptes oversight mentions (FSC-62, metadata-first).

Drives ``build`` against constructed editorial mention entries + the sample crosswalk/ministry
reference, asserting golden rule #5: a mention resolves to its entity SIREN through the crosswalk
(operators) or ministry reference, or is reported as unresolved — never guessed. Also pins per-row
licence + provenance, and that the committed editorial mapping parses and resolves fully.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core.models import MentionType
from ingestion.crosswalk_io import load_crosswalk
from ingestion.transforms.cour_des_comptes import (
    DEFAULT_LICENSE,
    SOURCE_ID,
    MentionEntry,
    build,
    load_mention_entries,
    transform,
)
from ingestion.transforms.operateurs_etat import MinistryIndex

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _crosswalk():
    # Sample crosswalk: "Agence Alpha" -> 111111118 (accepted/auto).
    return load_crosswalk(FIXTURES / "crosswalk_sample.yaml")


def _ministries() -> MinistryIndex:
    # Sample reference: "Ministère Alpha" (code AA) -> 900000017.
    return MinistryIndex.load(FIXTURES / "ministeres_sample.yaml")


def test_build_resolves_operator_via_crosswalk_and_stamps_fields() -> None:
    entries = [
        MentionEntry(
            entity_denomination="Agence Alpha",
            report_ref="Rapport sur l'Agence Alpha",
            report_date="2025-03-25",
            mention_type=MentionType.rapport,
            url="https://www.ccomptes.fr/fr/publications/agence-alpha",
            note="Observations définitives.",
        )
    ]
    result = build(entries, crosswalk=_crosswalk(), ministries=_ministries())
    assert len(result.mentions) == 1
    m = result.mentions[0]
    assert m.entity_siren == "111111118"  # resolved via the operator crosswalk
    assert m.mention_type is MentionType.rapport
    assert m.report_date == "2025-03-25"
    assert (m.url or "").startswith("https://")
    assert m.provenance == SOURCE_ID
    assert m.license == DEFAULT_LICENSE  # default applied when the entry omits it
    assert result.report["unresolved"] == 0
    assert result.report["resolution_rate"] == 1.0


def test_build_resolves_ministry_via_reference_fallback() -> None:
    entries = [
        MentionEntry(
            entity_denomination="Ministère Alpha",
            report_ref="Rapport ministériel",
            report_date="2024-01-01",
            mention_type=MentionType.recommandation,
            url="https://www.ccomptes.fr/fr/publications/min-alpha",
            license="ODbL",
        )
    ]
    result = build(entries, crosswalk=_crosswalk(), ministries=_ministries())
    assert result.mentions[0].entity_siren == "900000017"  # ministry-reference fallback
    assert result.mentions[0].license == "ODbL"  # per-row override respected


def test_build_routes_unresolved_to_report_never_guesses() -> None:
    entries = [
        MentionEntry(
            entity_denomination="Entité Inconnue",
            report_ref="Rapport X",
            report_date="2023-06-01",
            mention_type=MentionType.rapport,
            url="https://www.ccomptes.fr/fr/publications/x",
        )
    ]
    result = build(entries, crosswalk=_crosswalk(), ministries=_ministries())
    assert result.mentions == []  # never attached to a guessed SIREN
    assert result.report["unresolved"] == 1
    assert result.report["resolution_rate"] == 0.0


def test_committed_editorial_file_parses_and_resolves_fully() -> None:
    entries = load_mention_entries()
    assert len(entries) >= 3
    assert all(e.url.startswith("https://www.ccomptes.fr") for e in entries)
    result = transform([], [])  # registered entry point: committed mapping + real crosswalk
    assert result.report["unresolved"] == 0
    assert len(result.mentions) == len(entries)
    assert {m.mention_type for m in result.mentions} <= {
        MentionType.rapport,
        MentionType.recommandation,
    }


def test_loader_rejects_invalid_mention_type(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema_version: 1\nentries:\n  - entity_denomination: X\n    report_ref: R\n"
        "    report_date: '2025-01-01'\n    mention_type: avis\n    url: https://x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mention_type"):
        load_mention_entries(bad)


def test_loader_rejects_non_http_url(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema_version: 1\nentries:\n  - entity_denomination: X\n    report_ref: R\n"
        "    report_date: '2025-01-01'\n    mention_type: rapport\n    url: javascript:alert(1)\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="http"):
        load_mention_entries(bad)
