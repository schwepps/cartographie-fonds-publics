"""resolve_entities: no silent drops, correct routing, honest rate, deterministic report."""

from __future__ import annotations

import json

import pytest
from core.crosswalk import Crosswalk, CrosswalkEntry, CrosswalkStatus
from core.models import Entity, Level
from core.resolution import ResolutionResult, UnresolvedReason, resolve_entities
from core.resolve import match_rate, normalize_name


def _entity(name: str, siren: str | None = None) -> Entity:
    return Entity(name=name, siren=siren, level=Level.state)


def _crosswalk() -> Crosswalk:
    return Crosswalk.from_entries(
        [
            CrosswalkEntry(
                denomination="Resolvable Op", status=CrosswalkStatus.reviewed, siren="180089013"
            ),
            CrosswalkEntry(
                denomination="Pending Op",
                status=CrosswalkStatus.pending,
                candidate_sirens=["111222333"],
            ),
            CrosswalkEntry(
                denomination="Ambiguous Op",
                status=CrosswalkStatus.pending,
                candidate_sirens=["111222333", "444555666"],
                top_match_ratio=0.9,
            ),
            CrosswalkEntry(
                denomination="Universités et assimilés", status=CrosswalkStatus.category
            ),
        ]
    )


@pytest.mark.parametrize(
    "entities",
    [
        [],
        [_entity("A", "180089013")],
        [_entity("Resolvable Op"), _entity("Pending Op"), _entity("Unknown Op")],
        [_entity("A", "180089013"), _entity("Ambiguous Op"), _entity("Universités et assimilés")],
    ],
)
def test_no_silent_drops(entities: list[Entity]) -> None:
    result = resolve_entities(entities, _crosswalk())
    assert len(result.resolved) + len(result.unresolved) == len(entities)
    assert result.total == len(entities)


def test_entity_with_siren_is_kept_untouched() -> None:
    entity = _entity("Has SIREN already", "775685019")
    result = resolve_entities([entity], _crosswalk())
    assert result.resolved == [entity]
    assert result.unresolved == []


def test_crosswalk_hit_fills_siren() -> None:
    result = resolve_entities([_entity("Resolvable Op")], _crosswalk())
    assert [e.siren for e in result.resolved] == ["180089013"]
    assert result.resolved[0].name == "Resolvable Op"  # other fields preserved


def test_unknown_entity_routed_no_crosswalk_reason() -> None:
    result = resolve_entities([_entity("Totally Unknown")], _crosswalk())
    assert result.resolved == []
    link = result.unresolved[0]
    assert link.reason is UnresolvedReason.no_siren_no_crosswalk
    assert link.normalized_name == normalize_name("Totally Unknown")


def test_pending_routed_with_pending_reason() -> None:
    link = resolve_entities([_entity("Pending Op")], _crosswalk()).unresolved[0]
    assert link.reason is UnresolvedReason.pending_review
    assert link.candidate_sirens == ["111222333"]


def test_multiple_candidates_reason() -> None:
    link = resolve_entities([_entity("Ambiguous Op")], _crosswalk()).unresolved[0]
    assert link.reason is UnresolvedReason.multiple_candidates
    assert link.top_match_ratio == 0.9


def test_category_label_reason() -> None:
    link = resolve_entities([_entity("Universités et assimilés")], _crosswalk()).unresolved[0]
    assert link.reason is UnresolvedReason.category_label


def test_resolution_rate_math_and_zero_guard() -> None:
    assert ResolutionResult().resolution_rate == 0.0  # zero-guard, no division error
    entities = [
        _entity("Resolvable Op"),
        _entity("Pending Op"),
        _entity("Unknown Op"),
        _entity("A", "180089013"),
    ]
    result = resolve_entities(entities, _crosswalk())
    assert result.resolution_rate == pytest.approx(2 / 4)  # Resolvable Op + the pre-SIREN'd A


def test_report_dict_is_json_serializable_timestamp_free_and_sorted() -> None:
    entities = [_entity("Pending Op"), _entity("Ambiguous Op"), _entity("Universités et assimilés")]
    report = resolve_entities(entities, _crosswalk()).to_report_dict()
    json.dumps(report)  # serializable
    assert "generated_at" not in report and "timestamp" not in report  # timestamp-free
    keys = [link["normalized_name"] for link in report["unresolved_links"]]
    assert keys == sorted(keys)  # stable output
    assert report["unresolved_by_reason"]["pending_review"] == 1


def test_report_is_deterministic_across_runs() -> None:
    entities = [_entity("Ambiguous Op"), _entity("Pending Op"), _entity("Unknown Op")]
    a = resolve_entities(entities, _crosswalk()).to_report_dict()
    b = resolve_entities(entities, _crosswalk()).to_report_dict()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_resolution_rate_distinct_from_set_match_rate() -> None:
    # resolution_rate = with-SIREN/total (per-run); match_rate = set overlap (cross-source).
    entities = [_entity("Resolvable Op"), _entity("Unknown Op")]
    result = resolve_entities(entities, _crosswalk())
    assert result.resolution_rate == pytest.approx(0.5)
    assert match_rate({"180089013"}, {"180089013", "999999999"}) == 1.0
