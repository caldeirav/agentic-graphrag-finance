"""Deterministic cross-period XBRL similarity edges."""

from datetime import date

from graph.builder import build_snapshot
from models.enums import GraphEdgeType, GraphNodeType
from models.filing import FilingRef, SectionBlock, TableBlock
from models.parsing import ParsedDocument


def _filing_doc(accession: str, period_end: date, concept_rows: list[list[str]]) -> ParsedDocument:
    filing = FilingRef(
        cik="0000320193",
        accession=accession,
        form_type="10-Q",
        filed_at=period_end,
        period_end=period_end,
        source_uri="fixture://",
    )
    return ParsedDocument(
        filing=filing,
        sections=[SectionBlock(section_id="s1", title="Facts")],
        tables=[TableBlock(table_id="xbrl-facts-1", headers=[], rows=concept_rows)],
        footnotes=[],
        parse_confidence=1.0,
        parser_version="test",
        content_hash=accession,
    )


def test_deterministic_similarity_links_revenue_across_filings():
    doc_a = _filing_doc(
        "0000320193-24-000001",
        date(2024, 6, 29),
        [["us-gaap:Revenue", "value:80"], ["", "period:2024-06-29"]],
    )
    doc_b = _filing_doc(
        "0000320193-24-000002",
        date(2024, 9, 28),
        [["us-gaap:Revenue", "value:95"], ["", "period:2024-09-28"]],
    )
    snap = build_snapshot("AAPL", [doc_a, doc_b], snapshot_id="sim-test")
    sim_edges = [e for e in snap.edges if e.edge_type == GraphEdgeType.SEMANTIC_SIMILARITY]
    assert sim_edges
    assert sim_edges[0].properties.get("link_method") == "deterministic"
    assert sim_edges[0].properties.get("concept_qname") == "us-gaap:Revenue"
    facts = [n for n in snap.nodes if n.node_type == GraphNodeType.CHUNK_XBRL_FACT]
    assert len(facts) >= 2
