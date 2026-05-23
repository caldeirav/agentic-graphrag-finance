"""Synthesis temporal anchor resolution after autonomous macro binding."""

from datetime import date

from models.enums import ComparisonMode, QueryStatus
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.macro.models import (
    BindingValidationResult,
    MacroBindingProposal,
    MacroBindingRecord,
    ProposalSource,
    ValidationStatus,
)
from retrieval.macro.pairing import infer_anchor_from_query
from retrieval.macro.validator import validate_macro_binding
from retrieval.synthesis import _correct_revenue_denial, _resolve_temporal_anchor


def test_infer_anchor_prior_quarter():
    assert infer_anchor_from_query("What was revenue in the prior quarter?") == "prior_quarter"


def test_infer_anchor_skips_qoq_phrase():
    assert infer_anchor_from_query("Quarter over quarter revenue change") is None


def test_resolve_temporal_anchor_from_macro_record(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    proposal = MacroBindingProposal(
        intent_summary="prior quarter",
        anchor="prior_quarter",
        proposal_source=ProposalSource.LLM,
    )
    validation = BindingValidationResult(
        status=ValidationStatus.APPROVED,
        approved_accessions=["0000320193-26-000006"],
        comparison_mode=ComparisonMode.SEQUENTIAL,
        rationale="ok",
    )
    record = MacroBindingRecord(
        binding_source="autonomous",
        proposal=proposal,
        validation=validation,
    )
    state = {
        "query": "What was revenue in the prior quarter?",
        "temporal_anchor": "",
        "macro_binding_record": record,
    }
    assert _resolve_temporal_anchor(state) == "prior_quarter"


def test_single_filing_comparison_mode_sequential(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    proposal = MacroBindingProposal(
        intent_summary="prior quarter",
        anchor="prior_quarter",
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(
        proposal, snap, query="revenue in the prior quarter"
    )
    assert result.status == ValidationStatus.APPROVED
    assert len(result.approved_accessions) == 1
    assert result.comparison_mode == ComparisonMode.SEQUENTIAL


def test_correct_revenue_denial_when_evidence_present():
    filing = FilingRef(
        cik="0000320193",
        accession="0000320193-26-000006",
        form_type="10-Q",
        filed_at=date(2026, 1, 30),
        period_end=date(2025, 12, 27),
        source_uri="u",
    )
    evidence = [
        EvidenceChunk(
            chunk_node_id="c1",
            excerpt=(
                "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: "
                "$143.76 billion USD for period 2025-09-28 - 2025-12-28"
            ),
            content_hash="h",
            accession=filing.accession,
        )
    ]
    bad = "Revenue for the prior quarter is not reported; only current quarter data exists."
    fixed = _correct_revenue_denial(
        bad,
        query="What was revenue in the prior quarter?",
        evidence=evidence,
        filing_set=[filing],
        temporal_anchor="prior_quarter",
        period_ends="2025-12-27",
    )
    assert "$143.76 billion" in fixed
    assert "not reported" not in fixed.lower()
