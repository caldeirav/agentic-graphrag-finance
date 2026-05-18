
from ingestion import fetch_filing
from ingestion.validators import validate_manifest
from models.ingestion import XBRLArtifactManifest


def test_fetch_filing_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_API_KEY", "test-mock")
    monkeypatch.setenv("SEC_DOWNLOADS_ROOT", str(tmp_path / "downloads"))
    from ingestion import settings

    settings.get_settings.cache_clear()

    entry = fetch_filing(ticker="AAPL", form_type="10-K")
    assert entry.local_path.exists()
    manifest = XBRLArtifactManifest.model_validate_json(entry.manifest_path.read_text())
    validate_manifest(manifest, entry.local_path)
    assert any(a.filename.endswith(".xml") for a in manifest.artifacts)
