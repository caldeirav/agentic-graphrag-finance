from pathlib import Path

import pytest

from ingestion.html_narrative import ingest_html_narrative, resolve_narrative_html
from ingestion.validators import ValidationError, validate_not_html_only_package
from models.ingestion import FilingResolution, XBRLArtifactManifest


@pytest.fixture
def aapl_resolution() -> FilingResolution:
    return FilingResolution(
        ticker="AAPL",
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=__import__("datetime").date(2024, 11, 1),
        period_end=__import__("datetime").date(2024, 9, 28),
        edgar_filing_url="fixture://AAPL/0000320193-24-000123",
    )


def test_resolve_inline_from_fixture(aapl_resolution: FilingResolution) -> None:
    root = Path("tests/fixtures/sec_downloads/AAPL/0000320193-24-000123")
    manifest = XBRLArtifactManifest.model_validate_json((root / "manifest.json").read_text())
    resolved = resolve_narrative_html(root, manifest)
    assert resolved is not None
    assert resolved.path.exists()


def test_ingest_html_success(aapl_resolution: FilingResolution) -> None:
    root = Path("tests/fixtures/sec_downloads/AAPL/0000320193-24-000123")
    status = ingest_html_narrative(aapl_resolution, root, skip=False)
    assert status.value == "success"
    manifest = XBRLArtifactManifest.model_validate_json((root / "manifest.json").read_text())
    assert manifest.html_narrative_status == "success"
    assert manifest.html_artifact_relpath


def test_html_only_package_rejected(tmp_path: Path) -> None:
    manifest = XBRLArtifactManifest.model_validate_json(
        """{
          "resolution": {
            "ticker": "X", "cik": "1", "accession": "1-1-1",
            "form_type": "10-K", "filed_at": "2024-01-01", "period_end": "2024-01-01"
          },
          "artifacts": [{"filename": "only.htm", "role": "filing_html"}],
          "complete": true
        }"""
    )
    (tmp_path / "only.htm").write_text("<html><body>test</body></html>")
    (tmp_path / "manifest.json").write_text(manifest.model_dump_json())
    with pytest.raises(ValidationError):
        validate_not_html_only_package(tmp_path, manifest)
