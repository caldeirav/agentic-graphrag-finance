from datetime import datetime

from pydantic import BaseModel, Field

from models.enums import GraphEdgeType, GraphNodeType
from models.filing import FilingRef


class GraphNode(BaseModel):
    node_id: str
    node_type: GraphNodeType
    label: str
    properties: dict[str, str | int | float | bool] = Field(default_factory=dict)
    source_ref: str = ""


class GraphEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    edge_type: GraphEdgeType
    properties: dict[str, str | int | float | bool] = Field(default_factory=dict)


class GraphManifest(BaseModel):
    created_at: datetime
    filing_refs: list[FilingRef]
    parser_version: str
    graph_builder_version: str
    storage_path: str
    node_count: int = 0
    edge_count: int = 0


class GraphSnapshot(BaseModel):
    snapshot_id: str
    issuer_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    manifest: GraphManifest
