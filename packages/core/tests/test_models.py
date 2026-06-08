import pytest
from core.models import Attribution, Edge, EdgeType, Entity, Level, Mention
from core.resolve import match_rate, normalize_siren
from pydantic import ValidationError


def test_normalize_siren():
    assert normalize_siren("180 089 013") == "180089013"
    assert normalize_siren("12345") is None
    assert normalize_siren(None) is None


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ({"1", "2"}, {"2", "3"}, 0.5),  # partial overlap
        (set(), {"1"}, 0.0),  # empty left — guards division by zero
        ({"1"}, {"1"}, 1.0),  # full overlap
        ({"1"}, {"2"}, 0.0),  # no overlap
    ],
)
def test_match_rate(left, right, expected):
    assert match_rate(left, right) == expected


def test_entity_normalizes_and_allows_none_siren():
    e = Entity(siren="180 089 013", name="CNRS", level=Level.state)
    assert e.level == Level.state
    assert e.siren == "180089013"  # normalized on input
    assert Entity(siren=None, name="Unresolved op", level=Level.state).siren is None


def test_entity_rejects_invalid_siren():
    with pytest.raises(ValidationError):
        Entity(siren="abc123", name="Bad", level=Level.state)


def test_entity_rejects_invalid_level():
    with pytest.raises(ValidationError):
        Entity(siren=None, name="X", level="unknown_level")


def test_edge_requires_valid_sirens():
    edge = Edge(source_siren="180089013", target_siren="130025265", type=EdgeType.funds)
    assert edge.source_siren == "180089013"
    with pytest.raises(ValidationError):
        Edge(source_siren="nope", target_siren="130025265", type=EdgeType.funds)


def test_attribution_and_mention_construct():
    assert Attribution(legal_ref="L.123", txt="competence").legal_ref == "L.123"
    assert Mention(report_ref="CdC-2025", note="cited").note == "cited"
