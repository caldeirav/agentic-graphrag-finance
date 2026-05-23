"""Macro routing: LLM proposal + deterministic validation."""

from __future__ import annotations

from datetime import date

from models.enums import ComparisonMode, QueryStatus
from models.filing import FilingRef
from models.query import AnswerPackage, MacroPlan, TemporalScope
from retrieval.macro.models import (
    MacroBindingRecord,
    MacroBindingProposal,
    ProposalSource,
    ValidationStatus,
)
from retrieval.macro.pairing import infer_anchor_from_query
from retrieval.macro.planner import plan_macro_binding
from retrieval.macro.validator import validate_macro_binding
from retrieval.orchestration.state import AgentState


def _refs_for_accessions(snapshot, accessions: list[str]) -> list[FilingRef]:
    acc_set = set(accessions)
    return [r for r in snapshot.manifest.filing_refs if r.accession in acc_set]


def _scope_error_message(validation) -> str:
    codes = ", ".join(validation.failure_codes) or "macro_binding_failed"
    return f"Macro binding failed ({codes}): {validation.rationale}"


def macro_router(state: AgentState, *, graph_api=None) -> dict:
    query = state["query"]
    snapshot_id = state["snapshot_id"]
    pre_bound = list(state.get("filing_set") or [])
    cli_prebound = bool(state.get("cli_prebound"))

    if graph_api is None:
        return {
            "macro_plan": MacroPlan(
                intent_summary=query[:200],
                temporal_scope=TemporalScope(
                    anchor_periods=[date.today()],
                    comparison_mode=ComparisonMode.YOY,
                ),
                rationale="graph_api unavailable",
            ),
            "filing_set": pre_bound,
            "macro_llm_skipped": True,
            "graph_traversal": [{"node_id": "macro", "stage": "macro"}],
        }

    snap = graph_api.get_snapshot(snapshot_id)
    binding_source = "cli_prebound" if cli_prebound and pre_bound else "autonomous"
    trace_patch: dict = {}

    if cli_prebound and pre_bound:
        proposal = MacroBindingProposal(
            intent_summary=query[:200],
            proposed_accessions=[r.accession for r in pre_bound],
            proposal_source=ProposalSource.CLI,
            is_comparison=len(pre_bound) >= 2,
        )
        validation = validate_macro_binding(
            proposal,
            snap,
            cli_bound=pre_bound,
            query=query,
        )
        macro_llm_skipped = True
    else:
        proposal, trace_patch = plan_macro_binding(query, snap)
        if not proposal.anchor:
            inferred = infer_anchor_from_query(query)
            if inferred:
                proposal = proposal.model_copy(update={"anchor": inferred})
        validation = validate_macro_binding(proposal, snap, query=query)
        macro_llm_skipped = False

    record = MacroBindingRecord(
        binding_source=binding_source,
        proposal=proposal,
        validation=validation,
        scope_manifest_id=snapshot_id,
    )

    if validation.status == ValidationStatus.FAILED:
        out = {
            "macro_plan": MacroPlan(
                intent_summary=proposal.intent_summary,
                temporal_scope=TemporalScope(
                    anchor_periods=[],
                    comparison_mode=validation.comparison_mode,
                ),
                rationale=validation.rationale,
                binding_source=binding_source,
            ),
            "filing_set": [],
            "macro_binding_record": record,
            "macro_binding_failed": True,
            "macro_llm_skipped": macro_llm_skipped,
            "answer": AnswerPackage(text=_scope_error_message(validation), citations=[]),
            "status": QueryStatus.ERROR,
            "graph_traversal": [{"node_id": "macro", "stage": "macro"}],
        }
        if trace_patch.get("trace_events"):
            out["trace_events"] = trace_patch["trace_events"]
        return out

    filing_refs = _refs_for_accessions(snap, validation.approved_accessions)
    record = record.model_copy(update={"filing_refs": filing_refs})

    anchor_periods = [f.period_end for f in filing_refs]
    plan = MacroPlan(
        intent_summary=proposal.intent_summary,
        temporal_scope=TemporalScope(
            anchor_periods=anchor_periods or [date.today()],
            comparison_mode=validation.comparison_mode,
        ),
        rationale=validation.rationale,
        binding_source=binding_source,
    )

    temporal_anchor = (proposal.anchor or infer_anchor_from_query(query) or "").strip()

    out = {
        "macro_plan": plan,
        "filing_set": filing_refs,
        "macro_binding_record": record,
        "macro_binding_failed": False,
        "macro_llm_skipped": macro_llm_skipped,
        "temporal_anchor": temporal_anchor,
        "graph_traversal": [{"node_id": "macro", "stage": "macro"}],
    }
    if trace_patch.get("trace_events"):
        out["trace_events"] = trace_patch["trace_events"]
    return out


# Re-export for tests that imported private helpers from this module
from retrieval.macro.llm_json import extract_json_from_llm as _extract_json_from_llm
from retrieval.macro.llm_json import parse_comparison_mode as _parse_comparison_mode

__all__ = ["macro_router", "_extract_json_from_llm", "_parse_comparison_mode"]
