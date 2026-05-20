"""GraphQueryAPI structural shortest path."""

from datetime import date
from pathlib import Path

from graph.builder import build_snapshot
from graph.query_api import LocalGraphQueryAPI
from models.filing import FilingRef, SectionBlock, TableBlock
from models.parsing import ParsedDocument


def test_query_api_structural_path(tmp_path: Path):
    filing = FilingRef(
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        source_uri="fixture://",
    )
    doc = ParsedDocument(
        filing=filing,
        sections=[SectionBlock(section_id="sec-1", title="MD&A")],
        tables=[TableBlock(table_id="xbrl-facts-1", headers=[], rows=[["c", "value:1"], ["", "period:p1"]])],
        footnotes=[],
        parse_confidence=1.0,
        parser_version="t",
        content_hash="h",
    )
    snap = build_snapshot("AAPL", [doc], snapshot_id="path-api-test")
    from graph.store import save_snapshot

    save_snapshot(snap, tmp_path)
    api = LocalGraphQueryAPI(tmp_path, "AAPL")
    doc_id = "doc-0000320193-24-000123"
    fact_id = next(n.node_id for n in snap.nodes if "xbrl-" in n.node_id)
    path = api.shortest_structural_path("path-api-test", doc_id, fact_id)
    assert path is not None
