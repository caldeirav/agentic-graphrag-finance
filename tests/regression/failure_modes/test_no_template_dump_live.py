"""Regression: live synthesis must not emit template chunk dumps (020)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from models.enums import EvidenceSourceType, QueryStatus
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.skills.structured_answer import StructuredAnswerPayload, is_chunk_dump_answer
from retrieval.synthesis import synthesize


def test_live_path_rejects_chunk_dump_from_llm(monkeypatch) -> None:
    monkeypatch.delenv("USE_MOCK_LLM", raising=False)
    filing = FilingRef(
        cik="320193",
        accession="0000320193-25-000123",
        form_type="10-K",
        filed_at=date(2025, 11, 1),
        period_end=date(2025, 9, 28),
        source_uri="",
    )
    evidence = [
        EvidenceChunk(
            chunk_node_id="doc-0000320193-25-000123-xbrl-1",
            excerpt=(
                "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: "
                "$416.16 billion USD for period 2024-09-29 - 2025-09-28"
            ),
            content_hash="abc",
            citation_label="xbrl:Revenue",
            accession="0000320193-25-000123",
            section_id="XBRL",
            source_type=EvidenceSourceType.XBRL,
        )
    ]
    dump_resp = MagicMock()
    dump_resp.content = "Based on 1 evidence chunk(s) from SEC filings:\n[1] ..."
    structured_resp = MagicMock()
    structured_resp.content = (
        '{"metric_label":"Revenue","value":"$416.16 billion","unit":"USD",'
        '"fiscal_period":"FY2025","concept":"RevenueFromContractWithCustomerExcludingAssessedTax",'
        '"citation_chunk_ids":["doc-0000320193-25-000123-xbrl-1"],"confidence":"high","abstain":false}'
    )
    call_count = {"n": 0}

    def fake_structured(*args, **kwargs):
        payload = StructuredAnswerPayload(
            metric_label="Revenue",
            value="$416.16 billion",
            unit="USD",
            fiscal_period="FY2025",
            concept="RevenueFromContractWithCustomerExcludingAssessedTax",
            citation_chunk_ids=["doc-0000320193-25-000123-xbrl-1"],
            confidence="high",
            abstain=False,
        )
        return payload, {}

    def fake_invoke(stage, llm, messages):
        call_count["n"] += 1
        if stage == "synthesize":
            return dump_resp, {}
        if stage == "synthesize_structured":
            return structured_resp, {}
        return dump_resp, {}

    with patch("retrieval.synthesis.traced_llm_invoke", side_effect=fake_invoke):
        with patch(
            "retrieval.synthesis.synthesize_structured_answer",
            side_effect=fake_structured,
        ):
            out = synthesize(
                {
                    "evidence_chunks": evidence,
                    "query": "What was revenue for fiscal year 2025?",
                    "filing_set": [filing],
                    "fiscal_period_labels_json": '["FY2025"]',
                    "temporal_anchor": "FY2025",
                }
            )
    assert not is_chunk_dump_answer(out["answer"].text)
    assert "416" in out["answer"].text
    assert out.get("synthesis_path") in ("structured_llm", "live_llm")


def test_live_path_abstains_instead_of_template_when_llm_empty(monkeypatch) -> None:
    monkeypatch.delenv("USE_MOCK_LLM", raising=False)
    filing = FilingRef(
        cik="320193",
        accession="0000320193-25-000123",
        form_type="10-K",
        filed_at=date(2025, 11, 1),
        period_end=date(2025, 9, 28),
        source_uri="",
    )
    evidence = [
        EvidenceChunk(
            chunk_node_id="c1",
            excerpt="XBRL RevenueFromContract: $10.00 billion USD",
            content_hash="h",
            source_type=EvidenceSourceType.XBRL,
            section_id="XBRL",
        )
    ]
    empty_resp = MagicMock()
    empty_resp.content = ""

    with patch("retrieval.synthesis.traced_llm_invoke", return_value=(empty_resp, {})):
        with patch("retrieval.synthesis.synthesize_structured_answer", return_value=(None, {})):
            out = synthesize(
                {
                    "evidence_chunks": evidence,
                    "query": "What was revenue?",
                    "filing_set": [filing],
                }
            )
    assert out["status"] == QueryStatus.INSUFFICIENT_EVIDENCE
    assert not is_chunk_dump_answer(out["answer"].text)
