"""LangGraph agent state."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from models.enums import QueryStatus
from models.filing import FilingRef
from models.query import (
    AnswerPackage,
    EvidenceChunk,
    IntentRouterTrace,
    MacroPlan,
    SectionCandidate,
)


def _merge_visits(left: list, right: list) -> list:
    return left + right


def _merge_trace_events(left: list, right: list) -> list:
    from tracing.console_trace.models import TraceEvent

    out: list[Any] = []
    for item in list(left or []) + list(right or []):
        if isinstance(item, TraceEvent):
            out.append(item)
        elif isinstance(item, dict):
            out.append(TraceEvent.model_validate(item))
    return out


class AgentState(TypedDict, total=False):
    query: str
    snapshot_id: str
    temporal_anchor: str
    macro_plan: MacroPlan | None
    intent_trace: IntentRouterTrace | None
    filing_set: list[FilingRef]
    section_candidates: list[SectionCandidate]
    evidence_chunks: list[EvidenceChunk]
    answer: AnswerPackage | None
    status: QueryStatus
    mlflow_run_id: str
    graph_traversal: Annotated[list, _merge_visits]
    trace_events: Annotated[list[Any], _merge_trace_events]
    trace_config: Any | None
    micro_ranked_count: int | None
    meso_section_trace: list[dict]
    micro_rank_trace: list[dict]
    macro_llm_skipped: bool | None
    macro_binding_record: Any | None
    macro_binding_failed: bool | None
    cli_prebound: bool | None
    binding_deferred: bool | None
    synthesis_retry_budget: bool | None
    variant_disable_macro_router: bool | None
    variant_disable_graph_walker: bool | None
    variant_xbrl_only: bool | None
    expected_section_paths_json: str | None
    suppress_benchmark_path_injection: bool | None
    fiscal_period_labels_json: str | None
    temporal_scope_intent_json: str | None
    metric_intent_json: str | None
    xbrl_resolution_json: str | None
    evidence_enrichment_json: str | None
    synthesis_path: str | None
    numeric_llm_fallback_blocked: bool | None
    html_fallback_used: bool | None
    navigation_trace: Any | None
