"""Pytest config for the Phase-0 spike tests.

Puts the spike package dir on ``sys.path`` (so ``import spike`` works without an installed
package) and exposes a ``load_fixture`` loader mirroring the ingestion test harness. HTTP is
mocked with respx's ``respx_mock`` fixture — no request ever leaves.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

SPIKE_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).parent / "fixtures"

if str(SPIKE_DIR) not in sys.path:
    sys.path.insert(0, str(SPIKE_DIR))


@pytest.fixture
def load_fixture() -> Callable[[str], bytes]:
    """Return a loader that reads a fixture file's raw bytes by name."""

    def _load(name: str) -> bytes:
        path = FIXTURES_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f"Fixture not found: {path}")
        return path.read_bytes()

    return _load
