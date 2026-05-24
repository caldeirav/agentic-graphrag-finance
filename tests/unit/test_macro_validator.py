"""Unit tests for macro validator (008)."""

from models.enums import ComparisonMode
from retrieval.macro.models import MacroBindingProposal, ProposalSource, ValidationStatus
from retrieval.macro.validator import validate_macro_binding
def test_validate_prior_quarter_approved(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    proposal = MacroBindingProposal(
        intent_summary="prior quarter revenue",
        anchor="prior_quarter",
        quarterly_metric_cue=True,
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(proposal, snap, query="revenue in the prior quarter")
    assert result.status == ValidationStatus.APPROVED
    assert len(result.approved_accessions) == 1
    assert result.approved_accessions[0] == "0000320193-26-000006"


def test_validate_yoy_explicit_annual_accessions_approved(aapl_macro_snapshot):
    """LLM-proposed 10-K pair must not be rejected by quarterly YoY re-pairing."""
    snap = aapl_macro_snapshot
    proposal = MacroBindingProposal(
        intent_summary="Compare total net sales year over year using annual reports.",
        comparison_mode=ComparisonMode.YOY,
        is_comparison=True,
        period_labels=["FY2025", "FY2024"],
        proposed_accessions=["0000320193-25-000079", "0000320193-24-000123"],
        quarterly_metric_cue=True,
        proposal_source=ProposalSource.LLM,
    )
    result = validate_macro_binding(
        proposal,
        snap,
        query="How did total net sales change year over year?",
    )
    assert result.status == ValidationStatus.APPROVED
    assert set(result.approved_accessions) == {
        "0000320193-25-000079",
        "0000320193-24-000123",
    }


def test_validate_yoy_quarterly_approved(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    proposal = MacroBindingProposal(
        intent_summary="yoy revenue",
        comparison_mode=ComparisonMode.YOY,
        is_comparison=True,
        quarterly_metric_cue=True,
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(proposal, snap, query="revenue year over year")
    assert result.status == ValidationStatus.APPROVED
    assert len(result.approved_accessions) == 2


def test_validate_qoq_approved(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    proposal = MacroBindingProposal(
        intent_summary="qoq",
        comparison_mode=ComparisonMode.QOQ,
        is_comparison=True,
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(proposal, snap, query="quarter over quarter")
    assert result.status == ValidationStatus.APPROVED
    assert len(result.approved_accessions) == 2


def test_validate_missing_yoy_partner_fails(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    # Drop prior-year quarter filing
    snap.manifest.filing_refs = [
        r for r in snap.manifest.filing_refs if r.accession != "0000320193-25-000073"
    ]
    proposal = MacroBindingProposal(
        intent_summary="yoy",
        comparison_mode=ComparisonMode.YOY,
        is_comparison=True,
        quarterly_metric_cue=True,
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(proposal, snap, query="revenue year over year")
    assert result.status == ValidationStatus.FAILED
    assert "missing_comparison_partner" in result.failure_codes


def test_validate_ambiguous_yoy_qoq_fails(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    proposal = MacroBindingProposal(
        intent_summary="mixed",
        comparison_mode=ComparisonMode.YOY,
        is_comparison=True,
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(
        proposal,
        snap,
        query="year over year and quarter over quarter revenue",
    )
    assert result.status == ValidationStatus.FAILED
    assert "ambiguous_comparison" in result.failure_codes
