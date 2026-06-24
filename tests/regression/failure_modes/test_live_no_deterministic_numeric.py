"""Regression: live synthesis must not inject deterministic numeric XBRL (021)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.synthesis import synthesize


def test_live_path_no_per_xbrl_deterministic_template(monkeypatch) -> None:
    monkeypatch.delenv("USE_MOCK_LLM", raising=False)
    filing = FilingRef(
        cik="34088",
        accession="0000034088-26-000067",
        form_type="10-K",
        filed_at=date(2026, 1, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    evidence = [
        EvidenceChunk(
            chunk_node_id="x1",
            excerpt="XBRL OtherAssetsFairValueDisclosure: $3.57 billion USD",
            content_hash="h",
            source_type=EvidenceSourceType.XBRL,
            section_id="XBRL",
        )
    ]
    refusal = MagicMock()
    refusal.content = "I cannot determine total assets from the evidence."

    with patch("retrieval.synthesis.traced_llm_invoke", return_value=(refusal, {})):
        with patch("retrieval.synthesis._try_computed_numeric_synthesis", return_value=None):
            with patch(
                "retrieval.synthesis.synthesize_structured_answer",
                return_value=(None, {}),
            ):
                out = synthesize(
                    {
                        "evidence_chunks": evidence,
                        "query": "What was the change in total assets?",
                        "filing_set": [filing],
                    }
                )
    text = out["answer"].text
    assert "Per XBRL" not in text
    assert "bound fiscal period" not in text
