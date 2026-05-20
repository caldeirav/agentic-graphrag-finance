"""LangGraph agent state."""

from __future__ import annotations

from typing import Annotated, TypedDict

from models.enums import QueryStatus
from models.filing import FilingRef
from models.query import (
    AnswerPackage,
    EvidenceChunk,
    MacroPlan,
    SectionCandidate,
)


def _merge_visits(left: list, right: list) -> list:
    return left + right


class AgentState(TypedDict, total=False):
    query: str
    snapshot_id: str
    temporal_anchor: str
    macro_plan: MacroPlan | None
    filing_set: list[FilingRef]
    section_candidates: list[SectionCandidate]
    evidence_chunks: list[EvidenceChunk]
    answer: AnswerPackage | None
    status: QueryStatus
    mlflow_run_id: str
    graph_traversal: Annotated[list, _merge_visits]
