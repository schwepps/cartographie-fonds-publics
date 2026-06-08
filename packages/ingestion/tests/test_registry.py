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


def test_schema_accessors_read_declared_schema():
    # DECP is the source that declares a Table Schema (schema.ref + schema.validate).
    decp = get_source("decp_commande_publique")
    assert decp.schema_ref == "https://schema.data.gouv.fr/"
    assert decp.schema_validate is True


def test_schema_accessors_tolerate_non_dict_schema():
    # Most sources set `schema` to a bare string (e.g. `none`) or omit it — must not raise.
    for src in sources():
        assert src.schema_ref is None or isinstance(src.schema_ref, str)
        assert isinstance(src.schema_validate, bool)


def test_schema_validate_false_without_usable_ref():
    src = Source(id="x", raw={"schema": "none"})
    assert src.schema_ref is None
    assert src.schema_validate is False
