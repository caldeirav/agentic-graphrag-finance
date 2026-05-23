"""Extended misalignment scenarios (US3 / SC-004)."""

from models.enums import ComparisonMode
from retrieval.macro.models import MacroBindingProposal, ProposalSource, ValidationStatus
from retrieval.macro.validator import validate_macro_binding


def test_ambiguous_yoy_and_qoq(aapl_macro_snapshot):
    proposal = MacroBindingProposal(
        intent_summary="mixed",
        comparison_mode=ComparisonMode.YOY,
        is_comparison=True,
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(
        proposal,
        aapl_macro_snapshot,
        query="year over year and quarter over quarter revenue",
    )
    assert result.status == ValidationStatus.FAILED
    assert "ambiguous_comparison" in result.failure_codes


def test_missing_prior_year_quarter_for_yoy(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    snap.manifest.filing_refs = [
        r
        for r in snap.manifest.filing_refs
        if r.accession not in ("0000320193-25-000057", "0000320193-25-000073")
    ]
    proposal = MacroBindingProposal(
        intent_summary="yoy q",
        comparison_mode=ComparisonMode.YOY,
        is_comparison=True,
        quarterly_metric_cue=True,
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(proposal, snap, query="revenue yoy latest quarter")
    assert result.status == ValidationStatus.FAILED
    assert "missing_comparison_partner" in result.failure_codes


def test_invalid_proposal_accession(aapl_macro_snapshot):
    proposal = MacroBindingProposal(
        intent_summary="bad",
        proposed_accessions=["0000000000-00-000000"],
        proposal_source=ProposalSource.LLM,
    )
    result = validate_macro_binding(proposal, aapl_macro_snapshot, query="revenue")
    assert result.status == ValidationStatus.FAILED


def test_empty_corpus_fails():
    from graph.legacy_builder import build_snapshot

    snap = build_snapshot("EMPTY", [], snapshot_id="empty")
    proposal = MacroBindingProposal(
        intent_summary="x",
        anchor="latest_quarter",
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(proposal, snap, query="revenue")
    assert result.status == ValidationStatus.FAILED
    assert "empty_corpus" in result.failure_codes
