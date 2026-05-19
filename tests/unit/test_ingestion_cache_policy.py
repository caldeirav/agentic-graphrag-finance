from ingestion.cache_manager import lookup_cache
from ingestion.package_utils import is_mock_package
from models.ingestion import (
    FilingResolution,
    XBRLArtifact,
    XBRLArtifactManifest,
    XBRLArtifactRole,
)


def test_is_mock_package_detects_mock_urls():
    manifest = XBRLArtifactManifest(
        resolution=FilingResolution(
            ticker="AAPL",
            cik="0000320193",
            accession="0000320193-24-000123",
            form_type="10-K",
            filed_at=__import__("datetime").date.today(),
            period_end=__import__("datetime").date.today(),
            sec_api_filing_url="https://sec.gov/mock/x",
        ),
        artifacts=[],
        complete=True,
    )
    assert is_mock_package(manifest)


def test_lookup_cache_ignores_mock_in_live_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_API_KEY", "real-key-not-mock")
    monkeypatch.setenv("SEC_DOWNLOADS_ROOT", str(tmp_path / "downloads"))
    from ingestion import settings

    settings.get_settings.cache_clear()

    resolution = FilingResolution(
        ticker="AAPL",
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=__import__("datetime").date.today(),
        period_end=__import__("datetime").date.today(),
        sec_api_filing_url="https://sec.gov/mock/x",
    )
    dest = tmp_path / "downloads" / "AAPL" / resolution.accession
    dest.mkdir(parents=True)
    (dest / "filing.html").write_text("x" * 6000)
    manifest = XBRLArtifactManifest(
        resolution=resolution,
        artifacts=[
            XBRLArtifact(filename="filing.html", role=XBRLArtifactRole.FILING_HTML),
        ],
        complete=True,
    )
    (dest / "manifest.json").write_text(manifest.model_dump_json())

    assert lookup_cache(resolution) is None
