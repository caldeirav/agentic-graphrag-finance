"""Resolve accession/section paths to section node ids in a snapshot."""

from __future__ import annotations

from evaluation.generation.section_paths import (
    item_number_key,
    normalize_section_key,
    parse_section_path,
)
from models.enums import GraphEdgeType, GraphNodeType
from models.graph import GraphNode, GraphSnapshot

RESOLVABLE_NODE_TYPES = frozenset(
    {
        GraphNodeType.SECTION,
        GraphNodeType.DOCUMENT,
    }
)


def _accession_matches(node: GraphNode, accession: str) -> bool:
    if not accession:
        return True
    node_key = node.node_id.replace("-", "")
    acc_key = accession.replace("-", "")
    return accession in node.node_id or acc_key in node_key


def _section_keys_for_node(node: GraphNode) -> set[str]:
    props = node.properties or {}
    keys = {
        normalize_section_key(node.label or ""),
        normalize_section_key(str(props.get("section_slug", ""))),
    }
    item_number = props.get("item_number")
    if item_number:
        keys.add(normalize_section_key(f"Item {item_number}"))
        keys.add(normalize_section_key(f"Item{item_number}"))
    return {k for k in keys if k}


def _section_matches(
    node: GraphNode,
    *,
    tail: str,
    tail_key: str,
    item_key: str | None,
) -> bool:
    node_label = node.label or ""
    node_label_key = normalize_section_key(node_label)
    node_keys = _section_keys_for_node(node)

    if tail and tail in node_label:
        return True
    if tail_key and node_label_key and (
        tail_key == node_label_key
        or tail_key.startswith(node_label_key)
        or node_label_key.startswith(tail_key)
    ):
        return True
    if item_key and item_key in node_keys:
        return True
    if item_key and any(
        key.startswith("item") and (key.startswith(item_key) or item_key.startswith(key))
        for key in node_keys
    ):
        return True
    return bool(tail_key and tail_key in node_keys)


def section_node_ids_for_path(snapshot: GraphSnapshot, section_path: str) -> list[str]:
    accession, tail = parse_section_path(section_path)
    tail_key = normalize_section_key(tail)
    item_key = item_number_key(tail_key)
    filing_accessions = {ref.accession for ref in snapshot.manifest.filing_refs}
    candidates: list[tuple[int, str]] = []

    for node in snapshot.nodes:
        if node.node_type not in RESOLVABLE_NODE_TYPES:
            continue
        if not _section_matches(node, tail=tail, tail_key=tail_key, item_key=item_key):
            continue
        if node.node_id == section_path or node.properties.get("section_path") == section_path:
            candidates.append((200, node.node_id))
            continue

        score = 0
        if accession and _accession_matches(node, accession):
            score += 100
        elif accession and accession in filing_accessions:
            score += 10
        elif not accession:
            score += 5
        else:
            continue

        node_label_key = normalize_section_key(node.label or "")
        if tail_key and tail_key == node_label_key:
            score += 20
        elif item_key and item_key in _section_keys_for_node(node):
            score += 15
        elif tail and tail in (node.label or ""):
            score += 12
        else:
            score += 5
        candidates.append((score, node.node_id))

    if not candidates and section_path in {n.node_id for n in snapshot.nodes}:
        return [section_path]
    if not candidates:
        return []
    best = max(score for score, _ in candidates)
    return sorted({node_id for score, node_id in candidates if score == best})


def chunk_ids_in_section_subtree(snapshot: GraphSnapshot, section_node_id: str) -> set[str]:
    """All evidence chunk node ids under a section via CONTAINS edges."""
    from collections import deque

    node_by_id = {n.node_id: n for n in snapshot.nodes}
    evidence_types = frozenset(
        {
            GraphNodeType.CHUNK_PARAGRAPH,
            GraphNodeType.CHUNK_XBRL_FACT,
            GraphNodeType.CHUNK_TABLE,
            GraphNodeType.CHUNK_ROW,
        }
    )
    out: set[str] = set()
    queue: deque[str] = deque([section_node_id])
    visited: set[str] = set()

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        node = node_by_id.get(current)
        if node is not None and node.node_type in evidence_types:
            out.add(current)
        for edge in snapshot.edges:
            if edge.edge_type != GraphEdgeType.CONTAINS:
                continue
            if edge.source_id == current and edge.target_id not in visited:
                queue.append(edge.target_id)
    return out
