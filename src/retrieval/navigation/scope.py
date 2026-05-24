"""Section subtree scope for micro evidence collection (009-C)."""

from __future__ import annotations

from models.enums import GraphEdgeType
from models.graph import GraphSnapshot
from retrieval.navigation.validator import is_chunk_node


def chunk_ids_in_section_subtree(snapshot: GraphSnapshot, section_node_id: str) -> set[str]:
    """All chunk node IDs reachable from *section_node_id* via CONTAINS edges."""
    nodes_by_id = {n.node_id: n for n in snapshot.nodes}
    out: set[str] = set()
    stack = [section_node_id]
    seen: set[str] = set()
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        node = nodes_by_id.get(cur)
        if node is not None and is_chunk_node(node.node_type):
            out.add(cur)
        for edge in snapshot.edges:
            if edge.source_id == cur and edge.edge_type == GraphEdgeType.CONTAINS:
                stack.append(edge.target_id)
    # Footnotes attach via FOOTNOTE_OF (footnote → table), not CONTAINS from section root.
    for edge in snapshot.edges:
        if edge.edge_type == GraphEdgeType.FOOTNOTE_OF and edge.target_id in out:
            fn = nodes_by_id.get(edge.source_id)
            if fn is not None and is_chunk_node(fn.node_type):
                out.add(edge.source_id)
    return out


def narrative_kind_for_section_id(section_id: str) -> str:
    sid = section_id.lower()
    if "md_and_a" in sid or "mda" in sid:
        return "md_and_a"
    if "risk_factors" in sid or "html-risk" in sid:
        return "risk_factors"
    if "business_description" in sid:
        return "business_description"
    if "xbrl-facts" in sid:
        return "xbrl_bucket"
    return "other"
