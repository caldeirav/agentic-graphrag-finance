"""Read-only graph navigation API."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from graph.accession import accession_from_node_id, document_root_id
from graph.reachability import shortest_structural_path
from graph.store import load_snapshot
from models.enums import GraphEdgeType, GraphNodeType
from models.filing import FilingRef
from models.graph import GraphNode, GraphSnapshot

_NAVIGABLE_TYPES = {
    GraphNodeType.SECTION,
    GraphNodeType.CHUNK_TABLE,
    GraphNodeType.CHUNK_ROW,
    GraphNodeType.CHUNK_PARAGRAPH,
    GraphNodeType.CHUNK_XBRL_FACT,
}


class GraphQueryAPI(Protocol):
    def get_snapshot(self, snapshot_id: str) -> GraphSnapshot: ...
    def get_node(self, snapshot_id: str, node_id: str) -> GraphNode: ...
    def neighbors(
        self, snapshot_id: str, node_id: str, edge_types: list[GraphEdgeType]
    ) -> list[GraphNode]: ...
    def sections_for_filings(
        self, snapshot_id: str, filings: list[FilingRef]
    ) -> list[GraphNode]: ...
    def document_roots_for_filings(
        self, snapshot_id: str, filings: list[FilingRef]
    ) -> list[GraphNode]: ...
    def outgoing_edges(
        self, snapshot_id: str, node_id: str, edge_types: list[GraphEdgeType]
    ) -> list[tuple[GraphEdgeType, GraphNode]]: ...
    def navigable_node_count(
        self, snapshot_id: str, filings: list[FilingRef]
    ) -> int: ...


class LocalGraphQueryAPI:
    def __init__(self, base_dir: Path, issuer_id: str) -> None:
        self._base = base_dir
        self._issuer_id = issuer_id
        self._cache: dict[str, GraphSnapshot] = {}

    def get_snapshot(self, snapshot_id: str) -> GraphSnapshot:
        if snapshot_id not in self._cache:
            self._cache[snapshot_id] = load_snapshot(self._issuer_id, snapshot_id, self._base)
        return self._cache[snapshot_id]


class InMemoryGraphQueryAPI(LocalGraphQueryAPI):
    """Serve a pre-loaded composite snapshot (multi-issuer repro bundles)."""

    def __init__(self, snapshot: GraphSnapshot) -> None:
        super().__init__(Path("."), snapshot.issuer_id)
        self._snapshot = snapshot
        self._cache = {snapshot.snapshot_id: snapshot}

    def get_snapshot(self, snapshot_id: str) -> GraphSnapshot:
        if snapshot_id in self._cache:
            return self._cache[snapshot_id]
        return self._snapshot

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

    def document_roots_for_filings(
        self, snapshot_id: str, filings: list[FilingRef]
    ) -> list[GraphNode]:
        snap = self.get_snapshot(snapshot_id)
        roots: list[GraphNode] = []
        for filing in filings:
            rid = document_root_id(filing.accession)
            for node in snap.nodes:
                if node.node_id == rid:
                    roots.append(node)
                    break
        return roots

    def outgoing_edges(
        self, snapshot_id: str, node_id: str, edge_types: list[GraphEdgeType]
    ) -> list[tuple[GraphEdgeType, GraphNode]]:
        snap = self.get_snapshot(snapshot_id)
        allowed = set(edge_types)
        out: list[tuple[GraphEdgeType, GraphNode]] = []
        node_by_id = {n.node_id: n for n in snap.nodes}
        for edge in snap.edges:
            if edge.edge_type not in allowed:
                continue
            if edge.source_id == node_id and edge.target_id in node_by_id:
                out.append((edge.edge_type, node_by_id[edge.target_id]))
        return out

    def navigable_node_count(
        self, snapshot_id: str, filings: list[FilingRef]
    ) -> int:
        snap = self.get_snapshot(snapshot_id)
        accessions = {f.accession for f in filings}
        count = 0
        for node in snap.nodes:
            if node.node_type not in _NAVIGABLE_TYPES:
                continue
            acc = accession_from_node_id(node.node_id)
            if acc and acc in accessions:
                count += 1
        return count

    def shortest_structural_path(
        self,
        snapshot_id: str,
        from_doc_id: str,
        to_node_id: str,
        *,
        hop_budget: int = 6,
    ) -> tuple[list[str], list[str]] | None:
        snap = self.get_snapshot(snapshot_id)
        return shortest_structural_path(snap, from_doc_id, to_node_id, hop_budget=hop_budget)
