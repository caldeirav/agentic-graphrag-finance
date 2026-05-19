from ingestion.cache_manager import lookup_cache
from ingestion.package_utils import is_fixture_package
from models.ingestion import (
    FilingResolution,
    XBRLArtifact,
    XBRLArtifactManifest,
    XBRLArtifactRole,
)


def test_is_fixture_package_detects_fixture_urls():
    manifest = XBRLArtifactManifest(
        resolution=FilingResolution(
            ticker="AAPL",
            cik="0000320193",
            accession="0000320193-24-000123",
            form_type="10-K",
            filed_at=__import__("datetime").date.today(),
            period_end=__import__("datetime").date.today(),
            edgar_filing_url="fixture://AAPL/0000320193-24-000123",
        ),
        artifacts=[],
        complete=True,
    )
    assert is_fixture_package(manifest)


def test_lookup_cache_ignores_fixture_in_live_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_FIXTURE_INGESTION", "0")
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
        edgar_filing_url="fixture://AAPL/0000320193-24-000123",
    )
    dest = tmp_path / "downloads" / "AAPL" / resolution.accession
    dest.mkdir(parents=True)
    (dest / "000032019324000123_htm.xml").write_text("x" * 1200)
    (dest / "000032019324000123.xsd").write_text('<?xml version="1.0"?><schema/>')
    manifest = XBRLArtifactManifest(
        resolution=resolution,
        artifacts=[
            XBRLArtifact(
                filename="000032019324000123_htm.xml",
                role=XBRLArtifactRole.INSTANCE,
            ),
            XBRLArtifact(filename="000032019324000123.xsd", role=XBRLArtifactRole.SCHEMA),
        ],
        complete=True,
    )
    (dest / "manifest.json").write_text(manifest.model_dump_json())

    assert lookup_cache(resolution) is None
