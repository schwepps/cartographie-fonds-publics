"""Offline test for the Cour des comptes full-text → entity candidate linker (FSC-67).

No network: PDF text extraction + a pure gazetteer matcher over the sample crosswalk/ministry
fixtures. Proves text extraction (and its fail-loud), the gazetteer build + precision guards, the
word-boundary scan, resolve-vs-backlog routing (never guessed), and the coverage/match-rate report.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from core.crosswalk import CrosswalkEntry, CrosswalkStatus
from ingestion.crosswalk_io import load_entries, load_ministries
from ingestion.mentions_candidates_io import CANDIDATES_PATH, load_candidates, write_candidates
from ingestion.transforms.cour_des_comptes import MENTIONS_PATH
from ingestion.transforms.cour_des_comptes_extract import (
    DEFAULT_LICENSE,
    SOURCE_ID,
    ReportInput,
    build_candidates,
    build_gazetteer,
    extract_text,
    link_entities,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _crosswalk() -> list[CrosswalkEntry]:
    # Agence Alpha (auto, 111111118), Agence Beta (auto, 222222226), Agence Pending (pending),
    # Universités et assimilés (category).
    return load_entries(FIXTURES / "crosswalk_sample.yaml")


def _ministries() -> list[CrosswalkEntry]:
    return load_ministries(FIXTURES / "ministeres_sample.yaml")


def _gazetteer():  # type: ignore[no-untyped-def]
    return build_gazetteer(_crosswalk(), _ministries())


def _report(pdf: bytes) -> ReportInput:
    return ReportInput(
        url="https://www.ccomptes.fr/fr/publications/exemple",
        report_ref="Rapport exemple",
        report_date="2025-03-25",
        mention_type="rapport",
        pdf_bytes=pdf,
    )


def test_extract_text_reads_the_fixture_pdf(load_fixture) -> None:  # type: ignore[no-untyped-def]
    text = extract_text(load_fixture("ccomptes_sample.pdf"))
    assert "Agence Alpha" in text


def test_extract_text_fails_loud_on_non_pdf() -> None:
    with pytest.raises(ValueError, match="unreadable PDF"):
        extract_text(b"this is not a pdf")


def _make_pdf(*, encrypted: bool) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)  # a page with no text content
    if encrypted:
        writer.encrypt("secret")
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_extract_text_fails_loud_on_encrypted_pdf() -> None:
    with pytest.raises(ValueError, match="encrypted"):
        extract_text(_make_pdf(encrypted=True))


def test_extract_text_fails_loud_on_text_empty_pdf() -> None:
    # Scanned/image PDFs extract to empty text — must fail loud, never silently emit no candidates.
    with pytest.raises(ValueError, match="no extractable text"):
        extract_text(_make_pdf(encrypted=False))


def test_build_gazetteer_precision_guard_and_status_filter() -> None:
    entries = [
        CrosswalkEntry(denomination="Agence", status=CrosswalkStatus.auto, siren="111111118"),
        CrosswalkEntry(denomination="Agence Alpha", status=CrosswalkStatus.auto, siren="111111118"),
        CrosswalkEntry(denomination="Universités et assimilés", status=CrosswalkStatus.category),
    ]
    surfaces = {t.surface for t in build_gazetteer(entries, []).terms}
    assert "Agence Alpha" in surfaces  # >=2 tokens kept
    assert "Agence" not in surfaces  # single-token dropped (precision guard)
    assert "Universités et assimilés" not in surfaces  # category labels excluded


def test_link_entities_resolves_known_and_backlogs_pending(load_fixture) -> None:  # type: ignore[no-untyped-def]
    text = extract_text(load_fixture("ccomptes_sample.pdf"))
    cands = {
        c.entity_denomination: c for c in link_entities(text, _gazetteer(), report=_report(b""))
    }

    assert cands["Agence Alpha"].entity_siren == "111111118"
    assert cands["Agence Alpha"].resolution_status == "resolved"
    assert cands["Agence Alpha"].provenance == SOURCE_ID
    assert cands["Agence Alpha"].license == DEFAULT_LICENSE
    # Pending entity is surfaced but never given a guessed SIREN (golden rule #5).
    assert cands["Agence Pending"].entity_siren is None
    assert cands["Agence Pending"].resolution_status == "unresolved"


def test_word_boundary_prevents_substring_false_positive() -> None:
    text = "Le rapport cite uniquement l'Agence Alphabet, une entite fictive."
    cands = link_entities(text, _gazetteer(), report=_report(b""))
    # "Agence Alphabet" must not trigger an "Agence Alpha" match.
    assert all(c.entity_denomination != "Agence Alpha" for c in cands)


def test_build_candidates_reports_coverage_and_match_rate(load_fixture) -> None:  # type: ignore[no-untyped-def]
    pdf = load_fixture("ccomptes_sample.pdf")
    result = build_candidates(
        [_report(pdf)], crosswalk_entries=_crosswalk(), ministry_entries=_ministries()
    )
    by_name = {c.entity_denomination: c for c in result.candidates}
    assert by_name["Agence Alpha"].resolution_status == "resolved"
    assert by_name["Agence Beta"].resolution_status == "resolved"
    assert by_name["Agence Pending"].resolution_status == "unresolved"
    assert result.report["coverage_rate"] == 1.0
    # 2 of 3 candidates resolve (Pending is the backlog).
    assert result.report["match_rate"] == pytest.approx(2 / 3)


def test_candidate_backlog_round_trips(load_fixture, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    pdf = load_fixture("ccomptes_sample.pdf")
    result = build_candidates(
        [_report(pdf)], crosswalk_entries=_crosswalk(), ministry_entries=_ministries()
    )
    out = tmp_path / "candidates.yaml"
    write_candidates(result, out)
    original = {c.entity_denomination: c for c in result.candidates}
    loaded = {c.entity_denomination: c for c in load_candidates(out)}
    assert loaded["Agence Alpha"].entity_siren == "111111118"
    assert loaded["Agence Pending"].entity_siren is None
    # The precision signal + reviewer evidence must survive the write→read (falsy-drop guard).
    alpha = loaded["Agence Alpha"]
    assert alpha.match_count == original["Agence Alpha"].match_count >= 1
    assert alpha.note == original["Agence Alpha"].note != ""
    assert alpha.report_date == "2025-03-25"


def test_candidate_backlog_is_never_the_published_path() -> None:
    assert CANDIDATES_PATH != MENTIONS_PATH
    assert CANDIDATES_PATH.parent.name == "candidates"
