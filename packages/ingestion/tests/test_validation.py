"""Validation harness contract tests — offline (no network; respx blocks any stray request)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from ingestion.errors import (
    SchemaResolutionError,
    SchemaValidationError,
    UnsupportedFormatError,
)
from ingestion.validation import validate_extract

SOURCE = "decp_commande_publique"
SCHEMA_URL = "https://schema.example.test/decp.json"


def _schema_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "decp_schema.json")


def _json_schema_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "json_records.table-schema.json")


def test_valid_extract_passes(load_fixture: Callable[[str], bytes], fixtures_dir: Path) -> None:
    report = validate_extract(
        load_fixture("decp_valid.csv"), source_id=SOURCE, schema_ref=_schema_path(fixtures_dir)
    )
    assert not report.skipped
    assert report.cell_warning_count == 0


def test_missing_column_fails_loud(
    load_fixture: Callable[[str], bytes], fixtures_dir: Path
) -> None:
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_extract(
            load_fixture("decp_drift.csv"), source_id=SOURCE, schema_ref=_schema_path(fixtures_dir)
        )
    err = exc_info.value
    assert "nature" in err.missing_columns
    # The message must name the drifted column and the source (AC2: clear, actionable).
    assert "nature" in str(err)
    assert SOURCE in str(err)


def test_renamed_column_fails_loud(fixtures_dir: Path) -> None:
    # `nature` renamed to `categorie` -> frictionless reports an incorrect-label for `nature`.
    raw = (
        b"acheteur_siren,acheteur_nom,titulaire_siren,titulaire_nom,montant,categorie\n"
        b"180089013,CNRS,552081317,X SA,1000,marche\n"
    )
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_extract(raw, source_id=SOURCE, schema_ref=_schema_path(fixtures_dir))
    assert "nature" in exc_info.value.renamed_columns


def test_whole_column_type_mismatch_is_warning_not_fatal(fixtures_dir: Path) -> None:
    # `montant` (declared integer) is text on every row. Under the simplified policy, wrong-typed
    # VALUES are a data-quality warning surfaced in provenance, not column drift -> must NOT raise.
    raw = (
        b"acheteur_siren,acheteur_nom,titulaire_siren,titulaire_nom,montant,nature\n"
        b"180089013,CNRS,552081317,X SA,abc,marche\n"
        b"130005481,France Travail,402360494,Y SARL,def,marche\n"
        b"210900011,Commune,799999999,Z SARL,ghi,concession\n"
    )
    report = validate_extract(raw, source_id=SOURCE, schema_ref=_schema_path(fixtures_dir))
    assert report.cell_warning_count == 3


def test_single_bad_cell_is_a_warning_not_fatal(fixtures_dir: Path) -> None:
    # One bad `montant` out of three rows: data-quality noise, not column drift -> must NOT raise.
    raw = (
        b"acheteur_siren,acheteur_nom,titulaire_siren,titulaire_nom,montant,nature\n"
        b"180089013,CNRS,552081317,X SA,abc,marche\n"
        b"130005481,France Travail,402360494,Y SARL,840000,marche\n"
        b"210900011,Commune,799999999,Z SARL,2300000,concession\n"
    )
    report = validate_extract(raw, source_id=SOURCE, schema_ref=_schema_path(fixtures_dir))
    assert report.cell_warning_count == 1


def test_single_row_with_bad_cell_does_not_false_fatal(fixtures_dir: Path) -> None:
    # A 1-row extract with one messy cell must NOT be fatal (regression: the old c>=total_rows
    # heuristic wrongly raised here).
    raw = (
        b"acheteur_siren,acheteur_nom,titulaire_siren,titulaire_nom,montant,nature\n"
        b"180089013,CNRS,552081317,X SA,abc,marche\n"
    )
    report = validate_extract(raw, source_id=SOURCE, schema_ref=_schema_path(fixtures_dir))
    assert report.cell_warning_count == 1


def test_header_only_extract_passes(fixtures_dir: Path) -> None:
    raw = b"acheteur_siren,acheteur_nom,titulaire_siren,titulaire_nom,montant,nature\n"
    report = validate_extract(raw, source_id=SOURCE, schema_ref=_schema_path(fixtures_dir))
    assert not report.skipped
    assert report.cell_warning_count == 0


def test_empty_extract_fails_loud(fixtures_dir: Path) -> None:
    # A 0-byte extract has no header -> all columns missing -> column drift -> fatal.
    with pytest.raises(SchemaValidationError):
        validate_extract(b"", source_id=SOURCE, schema_ref=_schema_path(fixtures_dir))


def test_bom_prefixed_extract_passes(
    load_fixture: Callable[[str], bytes], fixtures_dir: Path
) -> None:
    raw = b"\xef\xbb\xbf" + load_fixture("decp_valid.csv")  # UTF-8 BOM must not break header match
    report = validate_extract(raw, source_id=SOURCE, schema_ref=_schema_path(fixtures_dir))
    assert report.cell_warning_count == 0


def test_unsupported_format_raises(fixtures_dir: Path) -> None:
    # csv + json + parquet are supported (FSC-47/FSC-38); anything else is a capability limit.
    with pytest.raises(UnsupportedFormatError):
        validate_extract(
            b"\x00", source_id=SOURCE, schema_ref=_schema_path(fixtures_dir), fmt="xlsx"
        )


def test_valid_json_extract_passes(
    load_fixture: Callable[[str], bytes], fixtures_dir: Path
) -> None:
    report = validate_extract(
        load_fixture("json_records_valid.json"),
        source_id="finances_locales_ofgl",
        schema_ref=_json_schema_path(fixtures_dir),
        fmt="json",
    )
    assert not report.skipped
    assert report.cell_warning_count == 0


def test_drifted_json_fails_loud(load_fixture: Callable[[str], bytes], fixtures_dir: Path) -> None:
    # The drift fixture drops the `montant` column entirely -> column drift -> fatal (same policy
    # as a drifted CSV), proving JSON gets the fail-loud-on-drift guarantee.
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_extract(
            load_fixture("json_records_drift.json"),
            source_id="finances_locales_ofgl",
            schema_ref=_json_schema_path(fixtures_dir),
            fmt="json",
        )
    assert "montant" in exc_info.value.missing_columns


def test_enveloped_json_unwraps_then_validates(
    load_fixture: Callable[[str], bytes], fixtures_dir: Path
) -> None:
    # The records live under `results` (ODS shape); record_path unwraps before validation.
    report = validate_extract(
        load_fixture("json_records_enveloped.json"),
        source_id="finances_locales_ofgl",
        schema_ref=_json_schema_path(fixtures_dir),
        fmt="json",
        record_path="results",
    )
    assert not report.skipped
    assert report.cell_warning_count == 0


def test_wrong_envelope_key_fails_loud(
    load_fixture: Callable[[str], bytes], fixtures_dir: Path
) -> None:
    # A misconfigured records_path is a malformed envelope -> fail loud, never a silent empty set.
    with pytest.raises(SchemaValidationError):
        validate_extract(
            load_fixture("json_records_enveloped.json"),
            source_id="finances_locales_ofgl",
            schema_ref=_json_schema_path(fixtures_dir),
            fmt="json",
            record_path="data",
        )


def test_empty_json_array_fails_loud(fixtures_dir: Path) -> None:
    # An empty array tabularises to a header-less CSV -> every schema column is missing -> column
    # drift -> fatal (the JSON analogue of test_empty_extract_fails_loud).
    with pytest.raises(SchemaValidationError):
        validate_extract(
            b"[]",
            source_id="finances_locales_ofgl",
            schema_ref=_json_schema_path(fixtures_dir),
            fmt="json",
        )


def test_no_schema_declared_skips_validation(load_fixture: Callable[[str], bytes]) -> None:
    report = validate_extract(load_fixture("decp_valid.csv"), source_id=SOURCE, schema_ref=None)
    assert report.skipped


def test_remote_schema_is_fetched_and_validated(
    load_fixture: Callable[[str], bytes], respx_mock
) -> None:
    respx_mock.get(SCHEMA_URL).mock(
        return_value=httpx.Response(200, content=load_fixture("decp_schema.json"))
    )
    report = validate_extract(
        load_fixture("decp_valid.csv"), source_id=SOURCE, schema_ref=SCHEMA_URL
    )
    assert not report.skipped


def test_unresolvable_schema_ref_raises_resolution_error(respx_mock) -> None:
    # A portal HTML page (not a TableSchema JSON) is a CONFIG fault, distinct from data drift.
    respx_mock.get(SCHEMA_URL).mock(
        return_value=httpx.Response(200, content=b"<html>not a schema</html>")
    )
    with pytest.raises(SchemaResolutionError):
        validate_extract(b"a,b\n1,2\n", source_id=SOURCE, schema_ref=SCHEMA_URL)
