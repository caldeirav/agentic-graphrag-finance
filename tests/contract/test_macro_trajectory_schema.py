"""Contract: macro trajectory required fields (008)."""

from retrieval.macro.models import (
    BindingValidationResult,
    MacroBindingProposal,
    MacroBindingRecord,
    ProposalSource,
    ValidationStatus,
)
_REQUIRED_KEYS = {
    "binding_source",
    "comparison_mode",
    "selected_accessions",
    "temporal_anchor_summary",
    "rationale",
    "proposal_source",
    "validation_status",
    "failure_codes",
    "proposal",
    "validation",
}


def test_macro_binding_record_trajectory_shape(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    ref = snap.manifest.filing_refs[0]
    validation = BindingValidationResult(
        status=ValidationStatus.APPROVED,
        approved_accessions=[ref.accession],
        rationale="ok",
    )
    record = MacroBindingRecord(
        binding_source="autonomous",
        proposal=MacroBindingProposal(
            intent_summary="test",
            anchor="latest_quarter",
            proposal_source=ProposalSource.DETERMINISTIC,
        ),
        validation=validation,
        filing_refs=[ref],
        scope_manifest_id=snap.snapshot_id,
    )
    payload = record.to_trajectory_dict()
    assert _REQUIRED_KEYS.issubset(payload.keys())
