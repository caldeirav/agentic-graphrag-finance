"""XBRL fact nodes: all period contexts materialized."""

from datetime import date

from graph.docling_graph_mapper import map_filing
from models.enums import GraphNodeType
from models.filing import FilingRef, SectionBlock, TableBlock
from models.parsing import ParsedDocument


def test_multiple_period_contexts_distinct_nodes():
    filing = FilingRef(
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        source_uri="fixture://",
    )
    rows = [
        ["us-gaap:Revenue", "value:100"],
        ["", "period:2024-09-28"],
        ["us-gaap:Revenue", "value:90"],
        ["", "period:2023-09-30"],
    ]
    doc = ParsedDocument(
        filing=filing,
        sections=[SectionBlock(section_id="s1", title="Facts")],
        tables=[TableBlock(table_id="xbrl-facts-1", headers=[], rows=rows)],
        footnotes=[],
        parse_confidence=1.0,
        parser_version="test",
        content_hash="x",
    )
    nodes, _, result, _ = map_filing(doc)
    assert result.status.value == "included"
    facts = [n for n in nodes if n.node_type == GraphNodeType.CHUNK_XBRL_FACT]
    assert len(facts) == 2
    periods = {n.properties.get("period") for n in facts}
    assert "2024-09-28" in periods
    assert "2023-09-30" in periods
