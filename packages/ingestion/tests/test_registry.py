import pytest
from ingestion.registry import Source, get_source, load_registry, sources


def test_registry_loads_and_ids_unique():
    data = load_registry()
    assert data["schema_version"] >= 1
    ids = [s.id for s in sources()]
    assert ids and len(ids) == len(set(ids))


def test_get_source_returns_known_source():
    first_id = sources()[0].id
    src = get_source(first_id)
    assert isinstance(src, Source)
    assert src.id == first_id


def test_get_source_unknown_raises():
    with pytest.raises(KeyError):
        get_source("__does_not_exist__")
