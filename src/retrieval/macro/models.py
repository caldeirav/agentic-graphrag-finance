"""Pydantic models for macro binding proposal and validation (008)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from models.enums import ComparisonMode
from models.filing import FilingRef


class ProposalSource(StrEnum):
    LLM = "llm"
    DETERMINISTIC = "deterministic"
    CLI = "cli"


class ValidationStatus(StrEnum):
    APPROVED = "approved"
    FAILED = "failed"
    NARROWED = "narrowed"


class MisalignmentCode(StrEnum):
    MISSING_COMPARISON_PARTNER = "missing_comparison_partner"
    AMBIGUOUS_COMPARISON = "ambiguous_comparison"
    CLI_NL_CONFLICT = "cli_nl_conflict"
    EMPTY_CORPUS = "empty_corpus"
    INVALID_ACCESSION = "invalid_accession"
    INVALID_PAIRING = "invalid_pairing"
    INVALID_PROPOSAL = "invalid_proposal"
    TEMPORAL_MISMATCH = "temporal_mismatch"


class MacroBindingProposal(BaseModel):
    intent_summary: str
    comparison_mode: ComparisonMode | None = None
    anchor: str | None = None
    period_labels: list[str] = Field(default_factory=list)
    proposed_accessions: list[str] = Field(default_factory=list)
    is_comparison: bool = False
    quarterly_metric_cue: bool = False
    proposal_source: ProposalSource = ProposalSource.LLM
    raw_llm_text: str = ""


class BindingValidationResult(BaseModel):
    status: ValidationStatus
    approved_accessions: list[str] = Field(default_factory=list)
    comparison_mode: ComparisonMode = ComparisonMode.YOY
    failure_codes: list[str] = Field(default_factory=list)
    rationale: str
    narrowed_from: list[str] = Field(default_factory=list)


class MacroBindingRecord(BaseModel):
    binding_source: str
    proposal: MacroBindingProposal | None = None
    validation: BindingValidationResult
    filing_refs: list[FilingRef] = Field(default_factory=list)
    scope_manifest_id: str = ""

    def to_trajectory_dict(self) -> dict:
        """Shape for macro_binding.json and console trace (contracts/macro-trajectory.md)."""
        validation = self.validation
        proposal = self.proposal
        anchor_summary = ""
        if proposal and proposal.anchor:
            anchor_summary = proposal.anchor
        elif proposal and proposal.period_labels:
            anchor_summary = ", ".join(proposal.period_labels)
        return {
            "binding_source": self.binding_source,
            "comparison_mode": validation.comparison_mode.value.lower(),
            "selected_accessions": list(validation.approved_accessions),
            "temporal_anchor_summary": anchor_summary,
            "rationale": validation.rationale,
            "proposal_source": (
                proposal.proposal_source.value if proposal else ProposalSource.CLI.value
            ),
            "validation_status": validation.status.value,
            "failure_codes": list(validation.failure_codes),
            "proposal": proposal.model_dump(mode="json") if proposal else None,
            "validation": validation.model_dump(mode="json"),
        }
