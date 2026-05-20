"""Reachability audit BFS and pass threshold."""

from datetime import date

from graph.builder import build_snapshot
from graph.reachability import audit_snapshot_reachability, shortest_structural_path
from models.filing import FilingRef, SectionBlock, TableBlock
from models.parsing import ParsedDocument


def _sample_snapshot():
    filing = FilingRef(
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        source_uri="fixture://",
    )
    rows = [["us-gaap:Revenue", "value:100"], ["", "period:2024-09-28"]]
    doc = ParsedDocument(
        filing=filing,
        sections=[SectionBlock(section_id="sec-1", title="MD&A", level=1, text="Body " * 30)],
        tables=[
            TableBlock(
                table_id="table-0",
                headers=[],
                rows=[["Cash", "29,943"]],
            ),
            TableBlock(table_id="xbrl-facts-1", headers=[], rows=rows),
        ],
        footnotes=[],
        parse_confidence=1.0,
        parser_version="test",
        content_hash="h",
    )
    return build_snapshot("AAPL", [doc], snapshot_id="reach-test")


def test_shortest_structural_path_reaches_xbrl_fact():
    snap = _sample_snapshot()
    doc_id = "doc-0000320193-24-000123"
    fact_id = next(n.node_id for n in snap.nodes if "xbrl-" in n.node_id)
    path = shortest_structural_path(snap, doc_id, fact_id, hop_budget=6)
    assert path is not None
    assert path[0][0] == doc_id
    assert path[1]


def test_audit_pass_rate_threshold():
    snap = _sample_snapshot()
    report = audit_snapshot_reachability(snap, sample_size=5, pass_threshold=0.95)
    assert report.sample_size <= 5
    assert 0.0 <= report.pass_rate <= 1.0
    assert report.hop_budget == 6
