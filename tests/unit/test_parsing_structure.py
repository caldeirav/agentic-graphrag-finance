from datetime import UTC, datetime

from models.ingestion import CacheEntry
from parsing.docling_pipeline import find_primary_parse_path, parse_filing_path
from parsing.sec_download_adapter import filing_ref_from_manifest, load_manifest


def test_xbrl_instance_parsed_with_docling(fixtures_downloads_root):
    manifest_path = (
        fixtures_downloads_root / "AAPL" / "0000320193-24-000123" / "manifest.json"
    )
    entry = CacheEntry(
        local_path=manifest_path.parent,
        manifest_path=manifest_path,
        content_hash="fixture",
        cached_at=datetime.now(UTC),
    )
    manifest = load_manifest(entry)
    filing = filing_ref_from_manifest(manifest)
    instance = find_primary_parse_path(entry.local_path, manifest)
    doc = parse_filing_path(instance, filing, package_root=entry.local_path)
    assert doc.parser_version.startswith("docling-xbrl")
    assert doc.sections
