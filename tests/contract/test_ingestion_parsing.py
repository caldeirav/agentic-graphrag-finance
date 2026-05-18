
from ingestion import fetch_filing
from models.ingestion import CacheEntry
from parsing.sec_download_adapter import parse_from_cache


def test_parse_from_mock_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_API_KEY", "test-mock")
    monkeypatch.setenv("SEC_DOWNLOADS_ROOT", str(tmp_path / "downloads"))
    from ingestion import settings

    settings.get_settings.cache_clear()
    entry = fetch_filing(ticker="AAPL", form_type="10-K")
    doc = parse_from_cache(entry, use_docling=False)
    assert doc.filing.cik == "0000320193"
    assert doc.sections


def test_parse_from_fixture(fixtures_downloads_root):
    manifest_path = (
        fixtures_downloads_root / "AAPL" / "0000320193-24-000123" / "manifest.json"
    )
    entry = CacheEntry(
        local_path=manifest_path.parent,
        manifest_path=manifest_path,
        content_hash="fixture",
        parse_ready=True,
        cached_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        cache_hit=True,
    )
    doc = parse_from_cache(entry, use_docling=False)
    assert doc.filing.accession == "0000320193-24-000123"
