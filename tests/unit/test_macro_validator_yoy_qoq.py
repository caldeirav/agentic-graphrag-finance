"""YoY/QoQ validator materialization (US2)."""

from models.enums import ComparisonMode
from retrieval.macro.models import MacroBindingProposal, ProposalSource, ValidationStatus
from retrieval.macro.validator import validate_macro_binding


def test_yoy_quarterly_materialization(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    proposal = MacroBindingProposal(
        intent_summary="yoy",
        comparison_mode=ComparisonMode.YOY,
        is_comparison=True,
        quarterly_metric_cue=True,
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(proposal, snap, query="revenue year over year")
    assert result.status == ValidationStatus.APPROVED
    assert len(result.approved_accessions) == 2
    assert "0000320193-26-000013" in result.approved_accessions
    assert any(
        a in result.approved_accessions
        for a in ("0000320193-25-000057", "0000320193-25-000073")
    )


def test_qoq_materialization(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    proposal = MacroBindingProposal(
        intent_summary="qoq",
        comparison_mode=ComparisonMode.QOQ,
        is_comparison=True,
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(proposal, snap, query="quarter over quarter revenue")
    assert result.status == ValidationStatus.APPROVED
    assert result.approved_accessions == [
        "0000320193-26-000013",
        "0000320193-26-000006",
    ]


def test_yoy_missing_partner_fail_closed(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    snap.manifest.filing_refs = [
        r
        for r in snap.manifest.filing_refs
        if r.accession not in ("0000320193-25-000057", "0000320193-25-000073")
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
