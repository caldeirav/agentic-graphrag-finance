"""Integration: structural graph has no orphan evidence on fixture parse."""

from datetime import UTC, datetime

from graph.builder import build_snapshot
from models.enums import GraphEdgeType, GraphNodeType
from models.ingestion import CacheEntry
from parsing.sec_download_adapter import parse_from_cache


def test_published_snapshot_no_orphan_evidence(tmp_path, fixtures_downloads_root):
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
    snap = build_snapshot("AAPL", [doc], snapshot_id="struct-int-test")
    evidence_types = {
        GraphNodeType.CHUNK_TABLE,
        GraphNodeType.CHUNK_ROW,
        GraphNodeType.CHUNK_PARAGRAPH,
        GraphNodeType.CHUNK_XBRL_FACT,
    }
    contains_up: dict[str, set[str]] = {}
    for e in snap.edges:
        if e.edge_type == GraphEdgeType.CONTAINS:
            contains_up.setdefault(e.target_id, set()).add(e.source_id)

    doc_root = f"doc-{doc.filing.accession}"
    for node in snap.nodes:
        if node.node_type not in evidence_types:
            continue
        seen: set[str] = set()
        stack = [node.node_id]
        ok = False
        while stack:
            cur = stack.pop()
            if cur == doc_root:
                ok = True
                break
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(contains_up.get(cur, ()))
        assert ok, f"orphan {node.node_id}"
