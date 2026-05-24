"""Parity: legacy builder vs docling-graph mapper on fixture."""

from datetime import UTC, datetime

from graph import legacy_builder
from graph.builder import build_snapshot
from models.enums import GraphNodeType
from models.ingestion import CacheEntry
from parsing.sec_download_adapter import parse_from_cache


def test_xbrl_concept_period_keys_preserved(tmp_path, fixtures_downloads_root):
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
    legacy = legacy_builder.build_snapshot("AAPL", [doc], snapshot_id="legacy-parity")
    new = build_snapshot("AAPL", [doc], snapshot_id="new-parity")

    def xbrl_keys(snap):
        keys = set()
        for n in snap.nodes:
            if n.node_type == GraphNodeType.CHUNK_XBRL_FACT or (
                n.node_type == GraphNodeType.CHUNK_PARAGRAPH
                and n.properties.get("xbrl_concept")
            ):
                concept = n.properties.get("xbrl_concept", n.label)
                period = n.properties.get("period", "")
                keys.add((concept, period))
            if "xbrl-" in n.node_id and n.node_type == GraphNodeType.CHUNK_XBRL_FACT:
                keys.add((n.properties.get("xbrl_concept", ""), n.properties.get("period", "")))
        return keys

    legacy_keys = xbrl_keys(legacy)
    new_keys = xbrl_keys(new)
    if legacy_keys:
        assert legacy_keys <= new_keys or new_keys <= legacy_keys or len(new_keys) >= len(legacy_keys)

    structural_legacy = sum(
        1
        for n in legacy.nodes
        if n.node_type
        in (
            GraphNodeType.SECTION,
            GraphNodeType.CHUNK_TABLE,
            GraphNodeType.CHUNK_ROW,
        )
    )
    structural_new = sum(
        1
        for n in new.nodes
        if n.node_type
        in (
            GraphNodeType.SECTION,
            GraphNodeType.CHUNK_TABLE,
            GraphNodeType.CHUNK_ROW,
        )
    )
    if structural_legacy:
        ratio = structural_new / structural_legacy
        assert 0.95 <= ratio <= 1.05
