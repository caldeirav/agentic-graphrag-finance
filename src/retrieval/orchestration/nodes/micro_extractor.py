"""Micro routing: chunk and cell extraction."""

from __future__ import annotations

import hashlib

from models.enums import GraphEdgeType, GraphNodeType
from models.query import EvidenceChunk
from retrieval.orchestration.state import AgentState


def micro_extractor(state: AgentState, *, graph_api) -> dict:
    snapshot_id = state["snapshot_id"]
    candidates = state.get("section_candidates") or []
    snap = graph_api.get_snapshot(snapshot_id)
    evidence: list[EvidenceChunk] = []
    visits = []

    section_ids = {c.section_node_id for c in candidates[:5]}
    for node in snap.nodes:
        if node.node_type not in (
            GraphNodeType.CHUNK_TABLE,
            GraphNodeType.CHUNK_ROW,
            GraphNodeType.CHUNK_PARAGRAPH,
        ):
            continue
        parent_section = _parent_section(snap, node.node_id)
        if parent_section not in section_ids and section_ids:
            continue
        excerpt = node.source_ref or node.label
        evidence.append(
            EvidenceChunk(
                chunk_node_id=node.node_id,
                excerpt=excerpt[:2000],
                content_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
                citation_label=node.label[:80],
            )
        )
        visits.append({"node_id": node.node_id, "stage": "micro"})

    return {"evidence_chunks": evidence[:20], "graph_traversal": visits}


def _parent_section(snap, node_id: str) -> str | None:
    for edge in snap.edges:
        if edge.target_id == node_id and edge.edge_type == GraphEdgeType.CONTAINS:
            for n in snap.nodes:
                if n.node_id == edge.source_id and n.node_type == GraphNodeType.SECTION:
                    return n.node_id
            if edge.source_id.startswith("doc-"):
                return edge.source_id
    return None
