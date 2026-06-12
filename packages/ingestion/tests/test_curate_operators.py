"""Tests for assisted operator curation (FSC-56).

The network is injected as a fake ``search`` function, so the accept/decline logic is pinned
offline and deterministically. The contract under test is golden rule #5: accept a SIREN only on a
single, unambiguous, *public-sector* match (exact name / sigle / containment); leave everything
ambiguous or unmatched in the `pending` backlog, never guessed.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import respx
import yaml
from core.crosswalk import CrosswalkEntry, CrosswalkStatus
from ingestion.cli import app
from ingestion.crosswalk_io import load_entries
from ingestion.curate_operators import (
    SearchFn,
    curate,
    propose,
    to_reviewed,
)
from typer.testing import CliRunner

runner = CliRunner()
_RECHERCHE_URL = "https://recherche-entreprises.api.gouv.fr/search"


def _pending(denomination: str, tutelle: str | None = None) -> CrosswalkEntry:
    return CrosswalkEntry(
        denomination=denomination, status=CrosswalkStatus.pending, tutelle=tutelle
    )


def _candidate(
    siren: str,
    nom_complet: str,
    *,
    sigle: str | None = None,
    nature: str = "7389",
    est_administration: bool | None = None,
) -> dict:
    return {
        "siren": siren,
        "nom_complet": nom_complet,
        "nom_raison_sociale": nom_complet,
        "sigle": sigle,
        "nature_juridique": nature,
        "complements": {"est_administration": est_administration},
    }


def _search_returning(*candidates: dict) -> SearchFn:
    return lambda _name: list(candidates)


def test_unique_public_containment_match_is_accepted() -> None:
    # The candidate's legal name contains every significant token of the operator name (a strict
    # superset, not equality) → containment match.
    entry = _pending("Musée Picasso", "MC")
    search = _search_returning(
        _candidate("180046252", "MUSEE NATIONAL PICASSO PARIS", nature="7389")
    )
    proposal = propose(entry, search)
    assert proposal.accepted
    assert proposal.siren == "180046252"
    assert proposal.signal == "containment"
    assert "recherche-entreprises" in (proposal.note or "")


def test_exact_name_match_is_accepted() -> None:
    # An acronym-stripped variant equals the candidate's legal name → exact (the strongest signal).
    entry = _pending("INRAE - Institut national de recherche pour l'agriculture", "MESR")
    search = _search_returning(
        _candidate("180070039", "Institut national de recherche pour l'agriculture", sigle="INRAE")
    )
    proposal = propose(entry, search)
    assert proposal.accepted
    assert proposal.siren == "180070039"
    assert proposal.signal == "exact"


def test_sigle_match_is_accepted() -> None:
    # A bare acronym operator with no expansion in its name matches only on the candidate's `sigle`.
    entry = _pending("INRAE", "MESR")
    search = _search_returning(
        _candidate("180070039", "INSTITUT NATIONAL DE RECHERCHE POUR L'AGRICULTURE", sigle="INRAE")
    )
    proposal = propose(entry, search)
    assert proposal.accepted
    assert proposal.siren == "180070039"
    assert proposal.signal == "sigle"


def test_multiple_public_matches_stay_pending() -> None:
    # Two distinct public CROUS share the sigle — ambiguous, so decline and record the candidates.
    entry = _pending("CROUS", "MESR")
    search = _search_returning(
        _candidate("186901567", "CROUS DE LYON", sigle="CROUS"),
        _candidate("186701224", "CROUS DE PARIS", sigle="CROUS"),
    )
    proposal = propose(entry, search)
    assert not proposal.accepted
    assert proposal.siren is None
    assert proposal.candidate_sirens == ["186701224", "186901567"]


def test_private_candidate_is_not_accepted() -> None:
    # A name-identical but PRIVATE candidate (nature 2xxx, not 4xxx/7xxx) is never accepted.
    entry = _pending("Maison de la Culture")
    search = _search_returning(_candidate("500000009", "MAISON DE LA CULTURE", nature="2320"))
    proposal = propose(entry, search)
    assert not proposal.accepted
    assert proposal.candidate_sirens == []


def test_est_administration_flag_makes_a_candidate_public() -> None:
    entry = _pending("Agence Nationale Exemple")
    search = _search_returning(
        _candidate("130000016", "AGENCE NATIONALE EXEMPLE", nature="9220", est_administration=True)
    )
    proposal = propose(entry, search)
    assert proposal.accepted
    assert proposal.siren == "130000016"


def test_no_candidates_stays_pending() -> None:
    proposal = propose(_pending("Opérateur Introuvable"), _search_returning())
    assert not proposal.accepted
    assert proposal.candidate_sirens == []


def test_to_reviewed_carries_source_and_provenance() -> None:
    entry = _pending("Université de Strasbourg", "MESR")
    proposal = propose(
        entry, _search_returning(_candidate("130018569", "UNIVERSITE DE STRASBOURG", nature="7383"))
    )
    reviewed = to_reviewed(
        entry, proposal, reviewed_by="curate-operators", reviewed_at="2026-06-12"
    )
    assert reviewed.status is CrosswalkStatus.reviewed
    assert reviewed.siren == "130018569"
    assert reviewed.tutelle == "MESR"  # preserved from the pending row
    assert reviewed.source == "api-curated"
    assert reviewed.reviewed_by == "curate-operators"
    assert reviewed.reviewed_at == "2026-06-12"
    assert "nature 7383" in (reviewed.notes or "")


def test_curate_promotes_pending_and_preserves_others() -> None:
    entries = [
        CrosswalkEntry(denomination="Already Auto", status=CrosswalkStatus.auto, siren="180089013"),
        CrosswalkEntry(
            denomination="Human Reviewed",
            status=CrosswalkStatus.reviewed,
            siren="130005481",
            reviewed_by="alice",
        ),
        _pending("Université de Strasbourg", "MESR"),
        _pending("Totally Unknown Operator"),
    ]

    def search(name: str) -> list[dict]:
        if name.startswith("Université"):
            return [_candidate("130018569", "UNIVERSITE DE STRASBOURG", nature="7383")]
        return []

    result = curate(entries, search, reviewed_by="curate-operators", reviewed_at="2026-06-12")
    by_name = {e.denomination: e for e in result.entries}

    # Pending with a unique public match → reviewed; the unmatched one stays pending.
    assert by_name["Université de Strasbourg"].status is CrosswalkStatus.reviewed
    assert by_name["Totally Unknown Operator"].status is CrosswalkStatus.pending
    # Non-pending rows pass through untouched — a human review is never downgraded.
    assert by_name["Already Auto"].status is CrosswalkStatus.auto
    assert by_name["Human Reviewed"].reviewed_by == "alice"

    assert result.report["pending_in"] == 2
    assert result.report["promoted_to_reviewed"] == 1
    assert result.report["still_pending"] == 1
    assert result.report["still_pending_names"] == ["Totally Unknown Operator"]


def test_curate_is_idempotent_on_already_reviewed() -> None:
    # Re-running over an output that has no pending rows changes nothing.
    reviewed = CrosswalkEntry(
        denomination="X",
        status=CrosswalkStatus.reviewed,
        siren="180089013",
        reviewed_by="curate-operators",
    )
    result = curate(
        [reviewed], _search_returning(), reviewed_by="curate-operators", reviewed_at="2026-06-12"
    )
    assert result.entries == [reviewed]
    assert result.report["promoted_to_reviewed"] == 0


# --------------------------------------------------------------------------- #
# CLI: coverage gate + curate-operators (real client wiring, mocked HTTP)
# --------------------------------------------------------------------------- #
def _write_crosswalk(path: Path, rows: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"schema_version": 1, "entries": rows}), encoding="utf-8")


def test_coverage_command_reports_and_gates(tmp_path: Path) -> None:
    cw = tmp_path / "cw.yaml"
    _write_crosswalk(
        cw,
        [
            {"denomination": "Alpha Org", "status": "auto", "siren": "180089013"},
            {"denomination": "Beta Org", "status": "reviewed", "siren": "130005481"},
            {"denomination": "Gamma Org", "status": "pending"},
            {"denomination": "Universités et assimilés", "status": "category"},
        ],
    )
    out = tmp_path / "cov.json"
    # 2 resolved of 3 operator rows (category excluded) = 67% — above a 0.5 floor.
    ok = runner.invoke(
        app, ["coverage", "--crosswalk", str(cw), "--out", str(out), "--min-rate", "0.5"]
    )
    assert ok.exit_code == 0, ok.output
    assert "coverage 66.7%" in ok.output or "coverage 67" in ok.output
    # Same data fails a 0.9 floor (gate surfaces the metric to CI).
    fail = runner.invoke(
        app, ["coverage", "--crosswalk", str(cw), "--out", str(out), "--min-rate", "0.9"]
    )
    assert fail.exit_code == 1


@respx.mock
def test_curate_operators_cli_apply_promotes_a_unique_public_match(tmp_path: Path) -> None:
    cw = tmp_path / "operateurs.yaml"
    _write_crosswalk(
        cw,
        [
            {"denomination": "Musée Picasso", "status": "pending", "tutelle": "MC"},
            {"denomination": "Already Reviewed", "status": "reviewed", "siren": "180089013"},
        ],
    )
    respx.get(_RECHERCHE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "siren": "180046252",
                        "nom_complet": "MUSEE NATIONAL PICASSO PARIS",
                        "nom_raison_sociale": "MUSEE NATIONAL PICASSO PARIS",
                        "sigle": None,
                        "nature_juridique": "7389",
                        "complements": {"est_administration": True},
                    }
                ]
            },
        )
    )
    result = runner.invoke(app, ["curate-operators", "--crosswalk", str(cw), "--apply"])
    assert result.exit_code == 0, result.output
    by_name = {e.denomination: e for e in load_entries(cw)}
    promoted = by_name["Musée Picasso"]
    assert promoted.status is CrosswalkStatus.reviewed
    assert promoted.siren == "180046252"
    assert promoted.source == "api-curated"
    assert promoted.tutelle == "MC"  # preserved


@respx.mock
def test_curate_operators_cli_dry_run_does_not_write(tmp_path: Path) -> None:
    cw = tmp_path / "operateurs.yaml"
    _write_crosswalk(cw, [{"denomination": "Musée Picasso", "status": "pending"}])
    before = cw.read_text(encoding="utf-8")
    respx.get(_RECHERCHE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "siren": "180046252",
                        "nom_complet": "MUSEE NATIONAL PICASSO PARIS",
                        "nature_juridique": "7389",
                    }
                ]
            },
        )
    )
    result = runner.invoke(app, ["curate-operators", "--crosswalk", str(cw)])  # no --apply
    assert result.exit_code == 0, result.output
    assert "would promote 1" in result.output
    assert cw.read_text(encoding="utf-8") == before  # untouched
