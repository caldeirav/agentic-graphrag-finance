"""Macro validator: YoY on single 10-K with XBRL periods."""

from __future__ import annotations

from datetime import date

from graph.legacy_builder import build_snapshot
from models.enums import ComparisonMode
from models.filing import FilingRef
from models.parsing import ParsedDocument
from retrieval.macro.models import MacroBindingProposal, ValidationStatus
from retrieval.macro.validator import validate_macro_binding


def test_yoy_revenue_single_10k_approved_for_in_filing_xbrl():
    refs = [
        FilingRef(
            cik="0000320193",
            accession="0000320193-25-000079",
            form_type="10-K",
            filed_at=date(2025, 10, 31),
            period_end=date(2025, 9, 27),
            source_uri="u1",
        ),
    ]
    docs = [
        ParsedDocument(
            filing=r,
            sections=[],
            tables=[],
            footnotes=[],
            parse_confidence=1.0,
            parser_version="test",
            content_hash=r.accession,
        )
        for r in refs
    ]
    snap = build_snapshot("AAPL", docs, snapshot_id="macro-yoy-1")
    proposal = MacroBindingProposal(
        intent_summary="YoY net sales",
        comparison_mode=ComparisonMode.YOY,
        is_comparison=True,
        proposed_accessions=["0000320193-25-000079"],
    )
    result = validate_macro_binding(
        proposal,
        snap,
        query="How did total net sales change year over year?",
    )
    assert result.status == ValidationStatus.APPROVED
    assert result.comparison_mode == ComparisonMode.YOY
