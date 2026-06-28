"""Unit tests for structured answer contract (020)."""

from __future__ import annotations

from retrieval.skills.structured_answer import (
    StructuredAnswerPayload,
    is_chunk_dump_answer,
    render_structured_answer,
)


def test_is_chunk_dump_answer_detects_template_dump() -> None:
    assert is_chunk_dump_answer("Based on 3 evidence chunk(s) from SEC filings:")
    assert not is_chunk_dump_answer("Total debt was $95.00 billion for FY2025.")


def test_render_structured_answer_numeric() -> None:
    payload = StructuredAnswerPayload(
        metric_label="Total revenue",
        value="$416.16 billion",
        unit="USD",
        fiscal_period="FY2024",
        concept="RevenueFromContractWithCustomerExcludingAssessedTax",
        citation_chunk_ids=["c1"],
        confidence="high",
        abstain=False,
    )
    text = render_structured_answer(payload)
    assert "Total revenue was $416.16 billion USD" in text
    assert "FY2024" in text
    assert "RevenueFromContract" in text


def test_render_structured_answer_abstain() -> None:
    payload = StructuredAnswerPayload(
        metric_label="n/a",
        value="n/a",
        citation_chunk_ids=[],
        confidence="low",
        abstain=True,
        abstain_reason="No matching XBRL fact for FY2025.",
    )
    text = render_structured_answer(payload)
    assert "Insufficient evidence" in text
    assert "FY2025" in text
