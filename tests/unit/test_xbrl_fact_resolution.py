"""Unit tests for XBRL fact resolution skill (020)."""

from __future__ import annotations

import os
from datetime import date

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.skills.xbrl_fact_resolution import (
    filter_evidence_by_resolution,
    resolve_xbrl_facts,
    XbrlFactResolutionResult,
)


def _xbrl_chunk(
    chunk_id: str,
    excerpt: str,
    *,
    accession: str = "0000320193-25-000123",
) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=chunk_id,
        excerpt=excerpt,
        content_hash="h",
        citation_label="XBRL",
        source_type=EvidenceSourceType.XBRL,
        accession=accession,
        section_id="XBRL",
    )


def test_mock_resolve_prefers_year_in_query(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    chunks = [
        _xbrl_chunk(
            "c2026",
            "XBRL RevenueFromContract: $95.00 billion USD for period 2026-01-01 - 2026-04-01",
        ),
        _xbrl_chunk(
            "c2025",
            "XBRL RevenueFromContract: $416.16 billion USD for period 2025-01-01 - 2025-12-31",
        ),
    ]
    filing = FilingRef(
        cik="320193",
        accession="0000320193-25-000123",
        form_type="10-K",
        filed_at=date(2025, 11, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    result, _ = resolve_xbrl_facts(chunks, "What was revenue in 2025?", [filing])
    assert result.selected_chunk_ids == ["c2025"]
    assert result.sufficient is True


def test_filter_evidence_keeps_non_xbrl() -> None:
    html = EvidenceChunk(
        chunk_node_id="html1",
        excerpt="MD&A narrative",
        content_hash="h",
        citation_label="MD&A",
        source_type=EvidenceSourceType.HTML,
    )
    xbrl = _xbrl_chunk("x1", "XBRL StockholdersEquity: $50.00 billion USD")
    resolution = XbrlFactResolutionResult(selected_chunk_ids=["x1"], sufficient=True)
    filtered = filter_evidence_by_resolution([html, xbrl], resolution)
    ids = {c.chunk_node_id for c in filtered}
    assert ids == {"html1", "x1"}
