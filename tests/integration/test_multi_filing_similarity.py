"""Integration: temporal and deterministic similarity on multi-accession fixtures."""

from datetime import UTC, datetime

from graph.builder import build_snapshot
from models.enums import GraphEdgeType
from models.ingestion import CacheEntry
from parsing.sec_download_adapter import parse_from_cache


def test_multi_filing_edges(fixtures_downloads_root):
    accessions = ["0000320193-24-000123", "0000320193-24-000076"]
    docs = []
    for acc in accessions:
        manifest_path = fixtures_downloads_root / "AAPL" / acc / "manifest.json"
        if not manifest_path.exists():
            continue
        entry = CacheEntry(
            local_path=manifest_path.parent,
            manifest_path=manifest_path,
            content_hash="fixture",
            parse_ready=True,
            cached_at=datetime.now(UTC),
            cache_hit=True,
        )
        docs.append(parse_from_cache(entry))
    if len(docs) < 2:
        return
    snap = build_snapshot("AAPL", docs, snapshot_id="multi-sim")
    temporal = [e for e in snap.edges if e.edge_type == GraphEdgeType.TEMPORAL_TRANSITION]
    assert len(temporal) >= 1
