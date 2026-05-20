from datetime import date

from pydantic import BaseModel, Field

from models.enums import ComparisonMode, QueryStatus, Sufficiency
from models.filing import FilingRef


class TemporalScope(BaseModel):
    anchor_periods: list[date]
    comparison_mode: ComparisonMode = ComparisonMode.YOY


class MacroPlan(BaseModel):
    intent_summary: str
    temporal_scope: TemporalScope
    rationale: str = ""


class SectionCandidate(BaseModel):
    section_node_id: str
    score: float
    path: list[str] = Field(default_factory=list)


class EvidenceChunk(BaseModel):
    chunk_node_id: str
    excerpt: str
    content_hash: str
    citation_label: str = ""


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
    document_route: list[FilingRef] = Field(default_factory=list)
    graph_traversal: list[GraphVisit] = Field(default_factory=list)
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    status: QueryStatus = QueryStatus.SUCCESS
