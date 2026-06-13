"""Offline CLI test for the candidate-extraction gates (FSC-66/67).

Proves `extract-mentions` fails loud (exit 1) on a zero-candidate run — a degraded extraction must
never pass the match-rate floor silently. respx blocks the network; the report PDF is the fixture.
"""

from __future__ import annotations

import httpx
import yaml
from ingestion.cli import app
from typer.testing import CliRunner

runner = CliRunner()
URL = "https://www.ccomptes.fr/fr/publications/exemple.pdf"


def test_extract_mentions_fails_loud_on_zero_candidates(load_fixture, respx_mock, tmp_path) -> None:  # type: ignore[no-untyped-def]
    respx_mock.get(URL).mock(
        return_value=httpx.Response(200, content=load_fixture("ccomptes_sample.pdf"))
    )
    # An empty crosswalk → the fixture PDF's entities resolve to nothing → 0 candidates.
    crosswalk = tmp_path / "empty_crosswalk.yaml"
    crosswalk.write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")
    reports = tmp_path / "reports.yaml"
    reports.write_text(
        yaml.safe_dump({"reports": [{"url": URL, "report_ref": "X", "mention_type": "rapport"}]}),
        encoding="utf-8",
    )
    out = tmp_path / "candidates.yaml"
    result = runner.invoke(
        app,
        [
            "extract-mentions",
            "--reports",
            str(reports),
            "--out",
            str(out),
            "--crosswalk",
            str(crosswalk),
        ],
    )
    assert result.exit_code == 1  # zero-candidate run must fail loud, not pass the floor
