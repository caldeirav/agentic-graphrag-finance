"""Regression: numeric XBRL deterministic synthesis (019 M2)."""

from __future__ import annotations

from datetime import date

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.synthesis import _try_synthesize_numeric_xbrl


def test_numeric_xbrl_extracts_revenue_value() -> None:
    evidence = [
        EvidenceChunk(
            chunk_node_id="c1",
            excerpt=(
                "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: "
                "$416.16 billion USD for period 2024-09-28"
            ),
            content_hash="h",
            source_type=EvidenceSourceType.XBRL,
            accession="0000320193-24-000123",
        )
    ]
    filing_set = [
        FilingRef(
            cik="320193",
            accession="0000320193-24-000123",
            form_type="10-K",
            filed_at=date(2024, 11, 1),
            period_end=date(2024, 9, 28),
            source_uri="",
        )
    ]
    result = _try_synthesize_numeric_xbrl(evidence, "What was revenue?", filing_set)
    assert result is not None
    text = result["answer"].text
    assert "416" in text
