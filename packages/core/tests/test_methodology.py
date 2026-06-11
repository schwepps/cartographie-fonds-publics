"""Tests for the anti-double-counting perimeter mapping (FSC-42)."""

from __future__ import annotations

from core.methodology import (
    LOLF,
    M57,
    SOCIAL,
    mixes_perimeters,
    universe_for_level,
    universe_for_nomenclature,
)
from core.models import Level, Nomenclature


def test_nomenclature_maps_to_universe() -> None:
    assert universe_for_nomenclature(Nomenclature.lolf) == LOLF
    assert universe_for_nomenclature(Nomenclature.m57) == M57
    assert universe_for_nomenclature(Nomenclature.m14) == M57  # M14 + M57 = same local universe
    assert universe_for_nomenclature(Nomenclature.social) == SOCIAL


def test_level_maps_to_universe_delegated_is_none() -> None:
    assert universe_for_level(Level.state) == LOLF
    assert universe_for_level(Level.local) == M57
    assert universe_for_level(Level.social) == SOCIAL
    assert universe_for_level(Level.delegated) is None  # a recipient, not a budget universe


def test_single_universe_is_not_mixed() -> None:
    assert mixes_perimeters([Nomenclature.lolf, Nomenclature.lolf]) is False
    assert mixes_perimeters([Nomenclature.m57, Nomenclature.m14]) is False  # same local universe
    assert mixes_perimeters([Level.state, Level.state]) is False


def test_crossing_universes_is_mixed() -> None:
    assert mixes_perimeters([Nomenclature.lolf, Nomenclature.m57]) is True
    assert mixes_perimeters([Level.state, Level.local]) is True
    assert mixes_perimeters([Nomenclature.lolf, Level.local]) is True  # mixed key types allowed


def test_delegated_alone_does_not_make_a_mix() -> None:
    assert mixes_perimeters([Level.state, Level.delegated]) is False
    assert mixes_perimeters([Level.delegated, Level.delegated]) is False
