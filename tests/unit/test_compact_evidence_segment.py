"""Unit: synthesis evidence compaction prefers segment/business chunks."""

from __future__ import annotations

from models.enums import EvidenceSourceType, QueryIntent
from models.query import EvidenceChunk
from retrieval.context_budget import compact_evidence_for_llm


def test_segment_query_prefers_business_chunks() -> None:
    chunks = [
        EvidenceChunk(
            chunk_node_id="doc-x-html-risk_factors-1-body",
            excerpt="Macroeconomic risk factors affect operations.",
            content_hash="a",
            source_type=EvidenceSourceType.HTML,
            section_id="html-risk_factors-1",
        ),
        EvidenceChunk(
            chunk_node_id="doc-x-html-business-1-body",
            excerpt="Braun is reported under the Grooming segment.",
            content_hash="b",
            source_type=EvidenceSourceType.HTML,
            section_id="html-business-1",
        ),
    ]
    compact = compact_evidence_for_llm(
        chunks,
        query="Which business segment includes Braun grooming products?",
        query_intent=QueryIntent.QUALITATIVE,
    )
    assert compact
    assert "Grooming" in compact[0].excerpt
