"""Pydantic models for graph-native navigation (009)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from models.enums import GraphEdgeType


class NavigationStage(StrEnum):
    MESO = "meso"
    MICRO = "micro"


class HopDirection(StrEnum):
    OUTGOING = "outgoing"
    INCOMING = "incoming"


class ProposalSource(StrEnum):
    LLM = "llm"
    MOCK = "mock"


class HopCandidate(BaseModel):
    target_node_id: str
    edge_type: GraphEdgeType
    direction: HopDirection = HopDirection.OUTGOING
    score: float = 0.0


class HopProposal(BaseModel):
    stage: NavigationStage
    source_node_id: str
    candidates: list[HopCandidate] = Field(default_factory=list)
    intent_note: str = ""
    proposal_source: ProposalSource = ProposalSource.LLM


class HopValidationResult(BaseModel):
    status: str
    approved_hop: NavigationVisit | None = None
    rejection_code: str = ""
    rationale: str = ""


class NavigationVisit(BaseModel):
    stage: NavigationStage
    source_node_id: str
    edge_type: GraphEdgeType
    target_node_id: str
    accession: str = ""
    hop_index: int = 0
    stop_reason: str = ""


class NavigationPath(BaseModel):
    root_node_id: str
    terminal_node_id: str
    visits: list[NavigationVisit] = Field(default_factory=list)
    edge_type_sequence: list[str] = Field(default_factory=list)
    chunk_node_ids: list[str] = Field(default_factory=list)


class MesoRankRecord(BaseModel):
    section_node_id: str
    accession: str
    rank: int
    score: float
    path: NavigationPath
    micro_eligible: bool = False


class NavigationTraceRecord(BaseModel):
    section_discovery_mode: str = "toc_planner"
    toc_plans: list[dict] = Field(default_factory=list)
    meso_paths: list[NavigationPath] = Field(default_factory=list)
    meso_ranks: list[MesoRankRecord] = Field(default_factory=list)
    micro_paths: list[NavigationPath] = Field(default_factory=list)
    rejected_proposals: list[dict] = Field(default_factory=list)
    visit_counts: dict[str, int] = Field(default_factory=dict)
    scan_ratio: float = 0.0
    budget_exhausted: bool = False
    structural_edge_types_used: list[str] = Field(default_factory=list)

    def to_trajectory_dict(self) -> dict:
        return {
            "section_discovery_mode": self.section_discovery_mode,
            "toc_plans": self.toc_plans,
            "meso_ranks": [
                {
                    "section_node_id": r.section_node_id,
                    "accession": r.accession,
                    "rank": r.rank,
                    "score": r.score,
                    "micro_eligible": r.micro_eligible,
                    "path": r.path.model_dump(mode="json"),
                }
                for r in self.meso_ranks
            ],
            "micro_paths": [p.model_dump(mode="json") for p in self.micro_paths],
            "rejected_proposals": self.rejected_proposals,
            "visit_counts": self.visit_counts,
            "scan_ratio": self.scan_ratio,
            "budget_exhausted": self.budget_exhausted,
            "structural_edge_types_used": self.structural_edge_types_used,
        }
