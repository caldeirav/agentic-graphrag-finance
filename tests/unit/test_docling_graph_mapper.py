"""Docling-graph mapper structural edges and fail-closed rules."""

from datetime import date

from graph.docling_graph_mapper import map_filing
from models.enums import GraphEdgeType, GraphNodeType
from models.filing import FilingRef, SectionBlock
from models.graph_audit import FilingMaterializationStatus
from models.parsing import ParsedDocument


def _doc(accession: str = "0000320193-24-000123") -> ParsedDocument:
    filing = FilingRef(
        cik="0000320193",
        accession=accession,
        form_type="10-K",
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        source_uri="fixture://",
    )
    return ParsedDocument(
        filing=filing,
        sections=[SectionBlock(section_id="sec-1", title="MD&A", level=1, text="Long body " * 20)],
        tables=[],
        footnotes=[],
        parse_confidence=1.0,
        parser_version="test",
        content_hash="abc",
    )


def test_contains_chain_from_document_to_section():
    nodes, edges, result, _ = map_filing(_doc())
    assert result.status == FilingMaterializationStatus.INCLUDED
    doc_id = "doc-0000320193-24-000123"
    sec_id = f"{doc_id}-sec-1"
    assert any(n.node_id == doc_id and n.node_type == GraphNodeType.DOCUMENT for n in nodes)
    assert any(
        e.edge_type == GraphEdgeType.CONTAINS and e.source_id == doc_id and e.target_id == sec_id
        for e in edges
    )


def test_fail_closed_zero_sections_and_no_xbrl():
    doc = _doc()
    doc = doc.model_copy(update={"sections": [], "tables": []})
    _, _, result, _ = map_filing(doc)
    assert result.status == FilingMaterializationStatus.FAILED
    assert "zero sections" in (result.failure_reason or "")
