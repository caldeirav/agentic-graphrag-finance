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
    synthesis_retry_budget: bool | None
