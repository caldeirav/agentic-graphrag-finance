"""Unit tests for EDGAR filing links (019)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from evaluation.reproduction.investigation.edgar_links import build_edgar_links, build_edgar_url


def test_build_edgar_url_aapl() -> None:
    url = build_edgar_url("320193", "0000320193-24-000123")
    assert url == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019324000123/0000320193-24-000123-index.htm"
    )


def test_missing_cik_emits_omission_reason(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/custom_judge/corpus/graphs/AAPL/ci-aapl-snapshot.manifest.json")
    graphs = tmp_path / "corpus" / "graphs" / "AAPL"
    graphs.mkdir(parents=True)
    shutil.copy(fixture, graphs / "ci-aapl-snapshot.manifest.json")
    links = build_edgar_links(tmp_path, ["0000320193-24-000123", "unknown-accession"])
    by_acc = {link.accession: link for link in links}
    assert by_acc["0000320193-24-000123"].url
    assert by_acc["unknown-accession"].link_omitted_reason == "missing_cik"
    assert not by_acc["unknown-accession"].url
