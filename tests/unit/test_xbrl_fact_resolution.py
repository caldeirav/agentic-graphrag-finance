"""Unit tests for XBRL fact resolution skill (020 / 023 M2)."""

from __future__ import annotations

import json
import os
from datetime import date
from unittest.mock import MagicMock, patch

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry
from retrieval.skills.xbrl_fact_resolution import (
    filter_evidence_by_resolution,
    resolve_xbrl_facts,
    resolve_xbrl_facts_from_catalog,
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


def _margin_catalog() -> list[XbrlFactCatalogEntry]:
    return [
        XbrlFactCatalogEntry(
            chunk_id="ni",
            concept="NetIncomeLoss",
            value_display="$36.00 billion",
            period_end="2025-12-31",
            is_annual=True,
            matches_query=True,
        ),
        XbrlFactCatalogEntry(
            chunk_id="rev",
            concept="Revenues",
            value_display="$413.00 billion",
            period_end="2025-12-31",
            is_annual=True,
            matches_query=True,
        ),
    ]


def test_mock_resolve_ratio_pair_returns_two_ids(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    intent = MetricIntent(metric_type="ratio", metric_label="Net profit margin", periods_needed=1)
    result, _ = resolve_xbrl_facts_from_catalog(
        _margin_catalog(),
        "What was net profit margin for fiscal year 2025?",
        [],
        metric_intent=intent,
    )
    assert result.sufficient is True
    assert len(result.selected_chunk_ids) == 2


def test_live_resolve_accepts_llm_ratio_pair(monkeypatch) -> None:
    monkeypatch.delenv("USE_MOCK_LLM", raising=False)
    intent = MetricIntent(metric_type="ratio", metric_label="Net profit margin", periods_needed=1)
    llm_payload = {
        "selected_chunk_ids": ["ni", "rev"],
        "rationale": "Net income over revenue for FY2025.",
        "sufficient": True,
    }
    mock_resp = MagicMock()
    mock_resp.content = json.dumps(llm_payload)

    with patch(
        "retrieval.skills.xbrl_fact_resolution.traced_llm_invoke",
        return_value=(mock_resp, {}),
    ):
        result, _ = resolve_xbrl_facts_from_catalog(
            _margin_catalog(),
            "What was net profit margin for fiscal year 2025?",
            [],
            metric_intent=intent,
        )

    assert result.selected_chunk_ids == ["ni", "rev"]
    assert result.sufficient is True


def test_live_resolve_marks_insufficient_when_llm_returns_one_id(monkeypatch) -> None:
    monkeypatch.delenv("USE_MOCK_LLM", raising=False)
    intent = MetricIntent(metric_type="ratio", metric_label="Net profit margin", periods_needed=1)
    mock_resp = MagicMock()
    mock_resp.content = json.dumps(
        {
            "selected_chunk_ids": ["ni"],
            "rationale": "Only net income found.",
            "sufficient": True,
        }
    )
    with patch(
        "retrieval.skills.xbrl_fact_resolution.traced_llm_invoke",
        return_value=(mock_resp, {}),
    ):
        result, _ = resolve_xbrl_facts_from_catalog(
            _margin_catalog(),
            "What was net profit margin for fiscal year 2025?",
            [],
            metric_intent=intent,
        )
    assert result.sufficient is False
