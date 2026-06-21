"""Regression: template-dump guard when XBRL evidence ranked (019 M3)."""

from __future__ import annotations

import os
from datetime import date

from models.enums import EvidenceSourceType, QueryStatus
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.synthesis import _has_ranked_xbrl_evidence, synthesize


def test_has_ranked_xbrl_evidence_detects_xbrl_chunks() -> None:
    chunks = [
        EvidenceChunk(
            chunk_node_id="c1",
            excerpt="Revenue 416.16",
            content_hash="h",
            source_type=EvidenceSourceType.XBRL,
        )
    ]
    assert _has_ranked_xbrl_evidence(chunks) is True


def test_mock_llm_prefers_numeric_path_over_template_dump(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    filing = FilingRef(
        cik="0000320193",
        accession="0000320193-26-000006",
        form_type="10-Q",
        filed_at=date(2026, 1, 30),
        period_end=date(2025, 12, 27),
        source_uri="https://example.com",
    )
    evidence = [
        EvidenceChunk(
            chunk_node_id="doc-0000320193-26-000006-xbrl-c1",
            excerpt=(
                "XBRL RevenueFromContract: $95.00 billion USD "
                "for period 2025-09-28 - 2025-12-27"
            ),
            content_hash="abc",
            citation_label="xbrl:Revenue",
            accession="0000320193-26-000006",
            section_id="XBRL",
            source_type=EvidenceSourceType.XBRL,
        )
    ]
    out = synthesize(
        {
            "evidence_chunks": evidence,
            "query": "What was revenue?",
            "filing_set": [filing],
        }
    )
    assert out.get("synthesis_path") == "numeric_xbrl_deterministic"
    assert out["status"] == QueryStatus.SUCCESS
    assert "95" in out["answer"].text
