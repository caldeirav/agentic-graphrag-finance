"""Read-only graph navigation API."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from graph.store import load_snapshot
from models.enums import GraphEdgeType, GraphNodeType
from models.filing import FilingRef
from models.graph import GraphNode, GraphSnapshot


class GraphQueryAPI(Protocol):
    def get_snapshot(self, snapshot_id: str) -> GraphSnapshot: ...
    def get_node(self, snapshot_id: str, node_id: str) -> GraphNode: ...
    def neighbors(
        self, snapshot_id: str, node_id: str, edge_types: list[GraphEdgeType]
    ) -> list[GraphNode]: ...
    def sections_for_filings(
        self, snapshot_id: str, filings: list[FilingRef]
    ) -> list[GraphNode]: ...


class LocalGraphQueryAPI:
    def __init__(self, base_dir: Path, issuer_id: str) -> None:
        self._base = base_dir
        self._issuer_id = issuer_id
        self._cache: dict[str, GraphSnapshot] = {}

    def get_snapshot(self, snapshot_id: str) -> GraphSnapshot:
        if snapshot_id not in self._cache:
            self._cache[snapshot_id] = load_snapshot(self._issuer_id, snapshot_id, self._base)
        return self._cache[snapshot_id]

    def get_node(self, snapshot_id: str, node_id: str) -> GraphNode:
        snap = self.get_snapshot(snapshot_id)
        for node in snap.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(f"node not found: {node_id}")

    def neighbors(
        self, snapshot_id: str, node_id: str, edge_types: list[GraphEdgeType]
    ) -> list[GraphNode]:
        snap = self.get_snapshot(snapshot_id)
        allowed = set(edge_types)
        target_ids = {
            e.target_id
            for e in snap.edges
            if e.source_id == node_id and e.edge_type in allowed
        }
        target_ids |= {
            e.source_id
            for e in snap.edges
            if e.target_id == node_id and e.edge_type in allowed
        }
        return [n for n in snap.nodes if n.node_id in target_ids]

    def sections_for_filings(
        self, snapshot_id: str, filings: list[FilingRef]
    ) -> list[GraphNode]:
        snap = self.get_snapshot(snapshot_id)
        accession_set = {f.accession for f in filings}
        doc_ids = {
            n.node_id
            for n in snap.nodes
            if n.node_type == GraphNodeType.DOCUMENT
            and any(acc in n.node_id for acc in accession_set)
        }
        sections = []
        for edge in snap.edges:
            if edge.edge_type == GraphEdgeType.CONTAINS and edge.source_id in doc_ids:
                for node in snap.nodes:
                    if node.node_id == edge.target_id and node.node_type == GraphNodeType.SECTION:
                        sections.append(node)
        return sections
