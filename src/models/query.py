from datetime import UTC, date, datetime

from pydantic import BaseModel, Field

from models.enums import (
    ComparisonMode,
    EvidenceSourceType,
    IntentSource,
    QueryIntent,
    QueryStatus,
    RouterFallbackReason,
    SourceBias,
    Sufficiency,
)
from models.filing import FilingRef


class TemporalScope(BaseModel):
    anchor_periods: list[date]
    comparison_mode: ComparisonMode = ComparisonMode.YOY


class MacroPlan(BaseModel):
    intent_summary: str
    temporal_scope: TemporalScope
    rationale: str = ""
    binding_source: str = ""


class SectionCandidate(BaseModel):
    section_node_id: str
    score: float
    path: list[str] = Field(default_factory=list)


class IntentRouterTrace(BaseModel):
    query_intent: QueryIntent
    intent_source: IntentSource
    source_bias_applied: SourceBias
    router_fallback_reason: RouterFallbackReason | None = None
    router_model_id: str = ""
    router_raw_label: str = ""
    router_latency_ms: int | None = None
    classified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvidenceChunk(BaseModel):
    chunk_node_id: str
    excerpt: str
    content_hash: str
    citation_label: str = ""
    source_type: EvidenceSourceType = EvidenceSourceType.XBRL
    accession: str = ""
    section_id: str = ""


class AnswerPackage(BaseModel):
    text: str
    citations: list[EvidenceChunk] = Field(default_factory=list)
    sufficiency: Sufficiency = Sufficiency.COMPLETE


class GraphVisit(BaseModel):
    node_id: str
    edge_id: str | None = None
    stage: str = "meso"
    path_edge_types: list[str] = Field(default_factory=list)
    path_node_ids: list[str] = Field(default_factory=list)


class TrajectoryRecord(BaseModel):
    plan: MacroPlan | None = None
    macro_binding: dict | None = None
    intent_router: IntentRouterTrace | None = None
    document_route: list[FilingRef] = Field(default_factory=list)
    graph_traversal: list[GraphVisit] = Field(default_factory=list)
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    status: QueryStatus = QueryStatus.SUCCESS
