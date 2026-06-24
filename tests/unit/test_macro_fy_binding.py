"""Macro router FY binding integration (021/022)."""

from __future__ import annotations

from datetime import date, datetime

from models.filing import FilingRef
from models.graph import GraphManifest, GraphSnapshot
from retrieval.macro.models import MacroBindingProposal, ProposalSource, ValidationStatus
from retrieval.macro.validator import validate_macro_binding
from retrieval.skills.temporal_scope import infer_temporal_scope_intent


def _snapshot_with_filings(*filings: FilingRef) -> GraphSnapshot:
    manifest = GraphManifest(
        created_at=datetime(2025, 1, 1),
        filing_refs=list(filings),
        parser_version="test",
        graph_builder_version="test",
        storage_path="/tmp",
    )
    return GraphSnapshot(
        snapshot_id="snap",
        issuer_id="XOM",
        nodes=[],
        edges=[],
        manifest=manifest,
    )


def test_validator_aligns_cli_prebound_to_fy2025_10k() -> None:
    fy25 = FilingRef(
        cik="34088",
        accession="0000034088-25-000079",
        form_type="10-K",
        filed_at=date(2025, 2, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    q1_26 = FilingRef(
        cik="34088",
        accession="0000034088-26-000067",
        form_type="10-Q",
        filed_at=date(2026, 4, 1),
        period_end=date(2026, 3, 31),
        source_uri="",
    )
    snap = _snapshot_with_filings(fy25, q1_26)
    query = "What was total equity for fiscal year 2025?"
    intent = infer_temporal_scope_intent(query, fiscal_period_labels=["FY2025"])
    proposal = MacroBindingProposal(
        intent_summary=query,
        proposed_accessions=[fy25.accession, q1_26.accession],
        proposal_source=ProposalSource.CLI,
    )
    result = validate_macro_binding(
        proposal,
        snap,
        cli_bound=[fy25, q1_26],
        query=query,
        temporal_intent=intent,
    )
    assert result.status in (ValidationStatus.APPROVED, ValidationStatus.NARROWED)
    assert result.approved_accessions == [fy25.accession]


def test_validator_rebinds_cli_to_calendar_2025_10k() -> None:
    wrong = FilingRef(
        cik="34088",
        accession="0000034088-26-000067",
        form_type="10-K",
        filed_at=date(2026, 5, 4),
        period_end=date(2026, 3, 31),
        source_uri="",
    )
    cal2025 = FilingRef(
        cik="34088",
        accession="0000034088-26-000045",
        form_type="10-K",
        filed_at=date(2026, 2, 18),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    snap = _snapshot_with_filings(wrong, cal2025)
    query = "What was total equity for fiscal year 2025?"
    intent = infer_temporal_scope_intent(query, fiscal_period_labels=["2025-FY"])
    proposal = MacroBindingProposal(
        intent_summary=query,
        proposed_accessions=[wrong.accession],
        proposal_source=ProposalSource.CLI,
    )
    result = validate_macro_binding(
        proposal,
        snap,
        cli_bound=[wrong],
        query=query,
        temporal_intent=intent,
    )
    assert result.status == ValidationStatus.NARROWED
    assert result.approved_accessions == [cal2025.accession]
    assert wrong.accession in result.narrowed_from
