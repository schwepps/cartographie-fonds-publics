"""Unit tests for the JSON → tabular-CSV view used by the validate/snapshot harness (FSC-47)."""

from __future__ import annotations

import json

import pytest
from ingestion.json_records import json_to_csv_bytes, records_to_csv_bytes, unwrap_records


def test_unwrap_top_level_array() -> None:
    raw = b'[{"a": "1"}, {"a": "2"}]'
    assert unwrap_records(raw, record_path=None) == [{"a": "1"}, {"a": "2"}]


def test_unwrap_envelope_key() -> None:
    raw = b'{"total": 1, "results": [{"a": "1"}]}'
    assert unwrap_records(raw, record_path="results") == [{"a": "1"}]


def test_unwrap_missing_envelope_key_fails_loud() -> None:
    raw = b'{"records": [{"a": "1"}]}'
    with pytest.raises(ValueError, match="results"):
        unwrap_records(raw, record_path="results")


def test_unwrap_non_array_value_fails_loud() -> None:
    with pytest.raises(ValueError, match="array of records"):
        unwrap_records(b'{"results": {"a": 1}}', record_path="results")


def test_unwrap_record_path_set_but_root_is_array_fails_loud() -> None:
    with pytest.raises(ValueError, match="root is list"):
        unwrap_records(b'[{"a": 1}]', record_path="results")


def test_unwrap_unparseable_json_fails_loud() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        unwrap_records(b"not json", record_path=None)


def test_unwrap_records_must_be_objects() -> None:
    with pytest.raises(ValueError, match="must be objects"):
        unwrap_records(b"[1, 2, 3]", record_path=None)


def test_empty_array_unwraps_to_empty_list_and_header_only_csv() -> None:
    # An empty extract is valid input here (the connector guards emptiness); it tabularises to a
    # header-less CSV, which the validate path then treats as column drift (see test_validation).
    assert unwrap_records(b"[]", record_path=None) == []
    assert records_to_csv_bytes([]) == b"\r\n"


def test_csv_header_is_union_with_first_seen_order() -> None:
    # Second record adds `c`; a field missing on a row becomes an empty cell, not a dropped column.
    csv = records_to_csv_bytes([{"a": "1", "b": "2"}, {"a": "3", "c": "4"}]).decode()
    lines = csv.splitlines()
    assert lines[0] == "a,b,c"
    assert lines[1] == "1,2,"  # `c` absent on row 1 -> empty cell
    assert lines[2] == "3,,4"  # `b` absent on row 2 -> empty cell


def test_csv_coerces_scalars_and_encodes_nested() -> None:
    csv = records_to_csv_bytes([{"n": 1000, "b": True, "z": None, "nested": {"k": "v"}}]).decode()
    rows = csv.splitlines()
    assert rows[0] == "n,b,z,nested"
    assert rows[1] == '1000,true,,"{""k"":""v""}"'  # csv-quoted JSON for the nested value


def test_json_to_csv_bytes_unwraps_then_tabularises() -> None:
    raw = json.dumps({"results": [{"siren": "200054781", "montant": 10}]}).encode()
    assert json_to_csv_bytes(raw, record_path="results").decode().splitlines() == [
        "siren,montant",
        "200054781,10",
    ]
