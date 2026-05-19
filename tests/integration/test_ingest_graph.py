
from graph.builder import build_snapshot
from graph.store import load_snapshot, save_snapshot
from models.ingestion import CacheEntry
from parsing.sec_download_adapter import parse_from_cache
from parsing.validators import validate_parsed_document


def test_ingest_build_roundtrip(tmp_path, fixtures_downloads_root):
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
    doc = parse_from_cache(entry)
    # Minimal CI fixture may not yield Docling tables; structure check is in unit tests.
    validate_parsed_document(doc, require_tables_for_forms=set())
    snap = build_snapshot("0000320193", [doc], snapshot_id="integration-001")
    save_snapshot(snap, tmp_path)
    loaded = load_snapshot("0000320193", "integration-001", tmp_path)
    assert len(loaded.nodes) == len(snap.nodes)
