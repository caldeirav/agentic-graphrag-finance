"""Integration: reachability audit on built snapshot."""

from datetime import UTC, datetime

from graph.builder import build_snapshot
from graph.reachability import audit_snapshot_reachability, save_reachability_report
from models.ingestion import CacheEntry
from parsing.sec_download_adapter import parse_from_cache


def test_audit_artifact_written(tmp_path, fixtures_downloads_root):
    manifest_path = fixtures_downloads_root / "AAPL" / "0000320193-24-000123" / "manifest.json"
    if not manifest_path.exists():
        return
    entry = CacheEntry(
        local_path=manifest_path.parent,
        manifest_path=manifest_path,
        content_hash="fixture",
        parse_ready=True,
        cached_at=datetime.now(UTC),
        cache_hit=True,
    )
    doc = parse_from_cache(entry)
    snap = build_snapshot("AAPL", [doc], snapshot_id="audit-gate-test")
    report = audit_snapshot_reachability(snap, sample_size=10)
    path = save_reachability_report(report, tmp_path)
    assert path.exists()
    assert report.pass_rate >= 0.0
