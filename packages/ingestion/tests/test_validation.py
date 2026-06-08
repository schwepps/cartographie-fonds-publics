"""Validation harness contract tests — offline (no network; respx blocks any stray request)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from ingestion.errors import SchemaResolutionError, SchemaValidationError
from ingestion.validation import validate_extract

SOURCE = "decp_commande_publique"
SCHEMA_URL = "https://schema.example.test/decp.json"


def _schema_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "decp_schema.json")


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


def test_whole_column_type_drift_fails_loud(fixtures_dir: Path) -> None:
    # `montant` is declared integer but is text on EVERY row -> field-level drift -> fatal.
    raw = (
        b"acheteur_siren,acheteur_nom,titulaire_siren,titulaire_nom,montant,nature\n"
        b"180089013,CNRS,552081317,X SA,abc,marche\n"
        b"130005481,France Travail,402360494,Y SARL,def,marche\n"
        b"210900011,Commune,799999999,Z SARL,ghi,concession\n"
    )
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_extract(raw, source_id=SOURCE, schema_ref=_schema_path(fixtures_dir))
    assert exc_info.value.type_drift_columns == ["montant"]


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
    assert report.cell_warning_samples  # a sample is retained for provenance


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
