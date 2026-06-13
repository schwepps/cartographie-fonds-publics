"""Offline test for the deterministic décret→ministry candidate linker (FSC-66).

No network: the linker is a pure token matcher over the reviewed ministry reference. Proves a known
ministry resolves to its SIREN, an unknown one is routed to the backlog (never guessed), an
ambiguous title stays unresolved, the match rate is reported, and the backlog round-trips and is
never the published editorial path.
"""

from __future__ import annotations

from pathlib import Path

from ingestion.crosswalk_io import load_ministries
from ingestion.transforms.legifrance_attributions import ATTRIBUTIONS_PATH
from ingestion.transforms.legifrance_candidates import (
    CANDIDATES_PATH,
    DEFAULT_LICENSE,
    SOURCE_ID,
    extract_attribution_candidates,
    load_candidates,
    write_candidates,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _ministries():  # type: ignore[no-untyped-def]
    # Sample reference: Ministère Alpha (AA -> 900000017), Ministère Gamma (GG -> 900000025).
    return load_ministries(FIXTURES / "ministeres_sample.yaml")


def _decree(title: str, content: str = "") -> dict[str, str]:
    return {
        "title": title,
        "url": "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000000000001",
        "date": "2025-10-30",
        "content": content,
    }


def test_matches_known_ministry_to_siren() -> None:
    decrees = [
        _decree(
            "Décret n° 2025-1016 du 29 octobre 2025 relatif aux attributions du ministre Alpha",
            content="Le ministre Alpha conduit la politique du Gouvernement.",
        )
    ]
    result = extract_attribution_candidates(decrees, ministries=_ministries())
    [candidate] = result.candidates
    assert candidate.status == "matched"
    assert candidate.entity_siren == "900000017"
    assert candidate.matched_tutelle == "AA"
    assert candidate.provenance == SOURCE_ID
    assert candidate.license == DEFAULT_LICENSE
    assert result.report["matched"] == 1
    assert result.report["match_rate"] == 1.0


def test_unknown_ministry_routes_to_backlog_never_guessed() -> None:
    decrees = [_decree("Décret ... relatif aux attributions du ministre Inconnu")]
    result = extract_attribution_candidates(decrees, ministries=_ministries())
    [candidate] = result.candidates
    assert candidate.status == "unresolved"
    assert candidate.entity_siren is None  # never a fabricated SIREN (golden rule #5)
    assert result.report["unresolved"] == 1
    assert result.report["match_rate"] == 0.0


def test_ambiguous_title_stays_unresolved_with_hints() -> None:
    decrees = [
        _decree("Décret ... relatif aux attributions du ministre Alpha et du ministre Gamma")
    ]
    result = extract_attribution_candidates(decrees, ministries=_ministries())
    [candidate] = result.candidates
    assert candidate.status == "unresolved"
    assert candidate.entity_siren is None
    # Both candidate ministries are surfaced as reviewer hints, none is chosen.
    assert set(candidate.candidate_sirens) == {"900000017", "900000025"}


def test_match_rate_reported_over_mixed_batch() -> None:
    decrees = [
        _decree("attributions du ministre Alpha"),
        _decree("attributions du ministre Inconnu"),
    ]
    result = extract_attribution_candidates(decrees, ministries=_ministries())
    assert result.report["total"] == 2
    assert result.report["matched"] == 1
    assert result.report["match_rate"] == 0.5


def test_backlog_round_trips_and_preserves_null_siren(tmp_path: Path) -> None:
    decrees = [
        _decree("attributions du ministre Alpha"),
        _decree("attributions du ministre Inconnu"),
    ]
    result = extract_attribution_candidates(decrees, ministries=_ministries())
    out = tmp_path / "candidates.yaml"
    write_candidates(result, out)
    loaded = load_candidates(out)
    by_status = {c.status: c for c in loaded}
    assert by_status["matched"].entity_siren == "900000017"
    assert by_status["unresolved"].entity_siren is None


def test_candidate_backlog_is_never_the_published_path() -> None:
    # The backlog must not be the reviewed editorial file the transform publishes.
    assert CANDIDATES_PATH != ATTRIBUTIONS_PATH
    assert CANDIDATES_PATH.parent.name == "candidates"
