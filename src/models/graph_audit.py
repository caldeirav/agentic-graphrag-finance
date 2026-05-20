"""Reachability audit and per-filing materialization result models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FilingMaterializationStatus(StrEnum):
    INCLUDED = "included"
    FAILED = "failed"


class FilingMaterializationResult(BaseModel):
    accession: str
    status: FilingMaterializationStatus
    failure_reason: str | None = None
    node_count: int = 0
    edge_count: int = 0
    unresolved_footnotes: int = 0
    unresolved_cross_refs: int = 0


class AuditEntry(BaseModel):
    node_id: str
    accession: str
    node_kind: str
    reachable: bool
    hop_count: int | None = None
    path_edge_types: list[str] = Field(default_factory=list)
    path_node_ids: list[str] = Field(default_factory=list)


class ReachabilityAuditReport(BaseModel):
    snapshot_id: str
    issuer_id: str
    hop_budget: int = 6
    sample_size: int = 0
    pass_rate: float = 0.0
    pass_threshold: float = 0.95
    audit_ready: bool = False
    structural_edge_types: list[str] = Field(default_factory=list)
    entries: list[AuditEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    builder_version: str = ""
