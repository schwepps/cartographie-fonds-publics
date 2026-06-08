"""Shared pytest fixtures for the ingestion test suite.

These power the offline connector contract-test harness: a fixtures loader plus
respx's own ``respx_mock`` fixture (registered automatically by the respx pytest
plugin) give every connector test recorded HTTP with no network. See
``connectors/README.md`` for the full template.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to the shared connector-test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def load_fixture() -> Callable[[str], bytes]:
    """Return a loader that reads a fixture file's raw bytes by name.

    Usage::

        def test_discovery(load_fixture, respx_mock):
            payload = load_fixture("datagouv_dataset_search.json")
    """

    def _load(name: str) -> bytes:
        path = FIXTURES_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f"Fixture not found: {path}")
        return path.read_bytes()

    return _load
