"""Agent trajectory snapshot models (010)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from models.enums import QueryStatus
from models.query import IntentRouterTrace

TRAJECTORY_SCHEMA_VERSION = "1.0.0"


class SynthesisPath(StrEnum):
    LIVE_LLM = "live_llm"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"
    TEMPLATE = "template"


class StageDecision(BaseModel):
    stage: str
    description: str
    selected: bool | None = None


class TrajectoryPlan(BaseModel):
    intent_summary: str
    steps_considered: list[StageDecision] = Field(default_factory=list)
    chosen_path_rationale: str
    rejected_alternatives: list[str] = Field(default_factory=list)


class FilingRouteEntry(BaseModel):
    accession: str
    form_type: str
    cik: str | None = None
    filed_at: str | None = None
    period_end: str | None = None
    fiscal_period_label: str | None = None


class GraphHop(BaseModel):
    hop_index: int
    stage: str
    node_id: str
    node_type: str
    edge_type: str
    edge_id: str | None = None
    accession_prefix: str


class EvidenceEntry(BaseModel):
    chunk_node_id: str
    content_hash: str
    citation_label: str
    source_type: str
    accession: str
    section_id: str | None = None
    in_prompt: bool = True


class AgentTrajectorySnapshot(BaseModel):
    schema_version: str = TRAJECTORY_SCHEMA_VERSION
    query_id: str
    query_text: str
    issuer_id: str = ""
    snapshot_id: str = ""
    evaluation_as_of: str = ""
    mlflow_run_id: str = ""
    mlflow_trace_id: str | None = None
    status: QueryStatus = QueryStatus.SUCCESS
    synthesis_path: SynthesisPath = SynthesisPath.TEMPLATE
    absent_reason: str | None = None
    plan: TrajectoryPlan
    document_route: list[FilingRouteEntry] = Field(default_factory=list)
    graph_traversal: list[GraphHop] = Field(default_factory=list)
    evidence: list[EvidenceEntry] = Field(default_factory=list)
    stage_timings_ms: dict[str, int] = Field(default_factory=dict)
    macro_binding: dict | None = None
    navigation_trace: dict | None = None
    intent_router: IntentRouterTrace | None = None
