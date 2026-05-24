"""CLI precedence tests for macro validator (FR-006)."""

from retrieval.macro.models import MacroBindingProposal, ProposalSource, ValidationStatus
from retrieval.macro.validator import validate_macro_binding


def test_cli_prebound_approved(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    cli = [snap.manifest.filing_refs[0]]
    proposal = MacroBindingProposal(
        intent_summary="cli",
        proposed_accessions=[cli[0].accession],
        proposal_source=ProposalSource.CLI,
    )
    result = validate_macro_binding(proposal, snap, cli_bound=cli, query="test")
    assert result.status == ValidationStatus.APPROVED
    assert result.approved_accessions == [cli[0].accession]


def test_cli_conflict_fails(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    cli = [snap.manifest.filing_refs[0]]
    other = snap.manifest.filing_refs[1].accession
    proposal = MacroBindingProposal(
        intent_summary="conflict",
        proposed_accessions=[other],
        proposal_source=ProposalSource.LLM,
    )
    result = validate_macro_binding(proposal, snap, cli_bound=cli, query="test")
    assert result.status == ValidationStatus.FAILED
    assert "cli_nl_conflict" in result.failure_codes
