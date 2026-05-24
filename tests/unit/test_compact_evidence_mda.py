"""Unit: synthesis evidence compaction keeps MD&A chunks for MD&A risk queries."""

from __future__ import annotations

from models.enums import EvidenceSourceType, QueryIntent
from models.query import EvidenceChunk
from retrieval.context_budget import compact_evidence_for_llm


def test_mda_risk_query_keeps_md_and_a_without_risk_in_excerpt():
    chunks = [
        EvidenceChunk(
            chunk_node_id="doc-x-html-md_and_a-2-body",
            excerpt="Item 7. Management Discussion and Analysis of financial condition.",
            content_hash="a",
            source_type=EvidenceSourceType.HTML,
            section_id="html-md_and_a-2",
        ),
        EvidenceChunk(
            chunk_node_id="doc-x-html-risk_factors-1-body",
            excerpt="Macroeconomic risk factors affect operations.",
            content_hash="b",
            source_type=EvidenceSourceType.HTML,
            section_id="html-risk_factors-1",
        ),
    ]
    compact = compact_evidence_for_llm(
        chunks,
        query="principal risk factors discussed in management discussion and analysis",
        query_intent=QueryIntent.QUALITATIVE,
    )
    assert compact
    assert all("md_and_a" in c.section_id for c in compact)
    assert "Management" in compact[0].excerpt
