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
    # DECP declares the committed authoritative Table Schema (schema.ref + schema.validate). The ref
    # is a repo-root-relative path to a real, loadable frictionless descriptor (FSC-31).
    from pathlib import Path

    from ingestion.validation import resolve_schema

    decp = get_source("decp_commande_publique")
    assert decp.schema_ref and decp.schema_ref.endswith(".json")
    assert decp.schema_validate is True
    repo_root = Path(__file__).resolve().parents[3]
    schema = resolve_schema(str(repo_root / decp.schema_ref))
    assert schema is not None and schema.has_field("montant")  # loads + has a depended-on column


def test_schema_accessors_tolerate_non_dict_schema():
    # Most sources set `schema` to a bare string (e.g. `none`) or omit it — must not raise.
    for src in sources():
        assert src.schema_ref is None or isinstance(src.schema_ref, str)
        assert isinstance(src.schema_validate, bool)


def test_schema_validate_false_without_usable_ref():
    src = Source(id="x", raw={"schema": "none"})
    assert src.schema_ref is None
    assert src.schema_validate is False
