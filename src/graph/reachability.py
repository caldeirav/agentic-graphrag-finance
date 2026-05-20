"""Stratified reachability audit for graph snapshots (004)."""

from __future__ import annotations

import random
import re
from collections import deque
from pathlib import Path

import yaml

from graph.docling_graph_mapper import DOCLING_GRAPH_MAPPER_VERSION
from graph.edge_catalog import AUDIT_EDGE_TYPES, STRUCTURAL_EDGE_TYPE_VALUES
from models.enums import GraphEdgeType, GraphNodeType
from models.graph import GraphSnapshot
from models.graph_audit import AuditEntry, ReachabilityAuditReport

_NUMERIC = re.compile(r"[\d,]+\.?\d*")
_ACCESSION_IN_DOC = re.compile(r"^doc-(\d{10}-\d{2}-\d{6})")


def load_audit_config(path: Path | None = None) -> dict:
    cfg_path = path or Path("configs/graph_audit.yaml")
    if not cfg_path.exists():
        return {
            "hop_budget": 6,
            "sample_size": 100,
            "pass_threshold": 0.95,
            "random_seed": 42,
        }
    return yaml.safe_load(cfg_path.read_text()) or {}


def _build_adjacency(snapshot: GraphSnapshot) -> dict[str, list[tuple[str, GraphEdgeType]]]:
    adj: dict[str, list[tuple[str, GraphEdgeType]]] = {}
    for edge in snapshot.edges:
        if edge.edge_type not in AUDIT_EDGE_TYPES:
            continue
        adj.setdefault(edge.source_id, []).append((edge.target_id, edge.edge_type))
        adj.setdefault(edge.target_id, []).append((edge.source_id, edge.edge_type))
    return adj


def shortest_structural_path(
    snapshot: GraphSnapshot,
    from_doc_id: str,
    to_node_id: str,
    *,
    hop_budget: int = 6,
) -> tuple[list[str], list[str]] | None:
    """BFS shortest path using structural edge types only; returns (node_ids, edge_types)."""
    adj = _build_adjacency(snapshot)
    if from_doc_id not in adj and from_doc_id != to_node_id:
        return None
    queue: deque[tuple[str, list[str], list[str]]] = deque([(from_doc_id, [from_doc_id], [])])
    visited = {from_doc_id}
    while queue:
        node, path_nodes, path_edges = queue.popleft()
        if len(path_edges) > hop_budget:
            continue
        if node == to_node_id:
            return path_nodes, [e.value for e in path_edges]
        for neighbor, etype in adj.get(node, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, path_nodes + [neighbor], path_edges + [etype]))
    return None


def _doc_id_for_node(node_id: str) -> str:
    m = _ACCESSION_IN_DOC.match(node_id)
    return m.group(0) if m else node_id.split("-")[0]


def _accession_from_doc_id(doc_id: str) -> str:
    m = _ACCESSION_IN_DOC.match(doc_id)
    return m.group(1) if m else doc_id.removeprefix("doc-")


def _is_numeric_table_row(node) -> bool:
    if node.node_type != GraphNodeType.CHUNK_ROW:
        return False
    text = node.source_ref or node.label or ""
    return bool(_NUMERIC.search(text))


def _stratified_sample(snapshot: GraphSnapshot, sample_size: int, seed: int) -> list:
    xbrl = [n for n in snapshot.nodes if n.node_type == GraphNodeType.CHUNK_XBRL_FACT]
    rows = [n for n in snapshot.nodes if _is_numeric_table_row(n)]
    min_xbrl = max(1, int(sample_size * 0.6))
    min_rows = max(0, sample_size - min_xbrl)
    rng = random.Random(seed)
    rng.shuffle(xbrl)
    rng.shuffle(rows)
    picked = xbrl[:min_xbrl]
    if len(picked) < sample_size:
        picked.extend(rows[: sample_size - len(picked)])
    if len(picked) < sample_size:
        extra = [n for n in snapshot.nodes if n not in picked and n.node_type in (
            GraphNodeType.CHUNK_XBRL_FACT,
            GraphNodeType.CHUNK_ROW,
        )]
        rng.shuffle(extra)
        picked.extend(extra[: sample_size - len(picked)])
    return picked[:sample_size]


def audit_snapshot_reachability(
    snapshot: GraphSnapshot,
    *,
    hop_budget: int | None = None,
    sample_size: int | None = None,
    pass_threshold: float | None = None,
    config: dict | None = None,
) -> ReachabilityAuditReport:
    cfg = config or load_audit_config()
    hop = hop_budget if hop_budget is not None else int(cfg.get("hop_budget", 6))
    size = sample_size if sample_size is not None else int(cfg.get("sample_size", 100))
    threshold = pass_threshold if pass_threshold is not None else float(cfg.get("pass_threshold", 0.95))
    seed = int(cfg.get("random_seed", 42))

    population = _stratified_sample(snapshot, size, seed)
    entries: list[AuditEntry] = []
    reachable_count = 0

    for node in population:
        doc_id = _doc_id_for_node(node.node_id)
        accession = _accession_from_doc_id(doc_id)
        kind = "xbrl_fact" if node.node_type == GraphNodeType.CHUNK_XBRL_FACT else "table_row"
        path = shortest_structural_path(snapshot, doc_id, node.node_id, hop_budget=hop)
        if path:
            path_nodes, path_edges = path
            reachable_count += 1
            entries.append(
                AuditEntry(
                    node_id=node.node_id,
                    accession=accession,
                    node_kind=kind,
                    reachable=True,
                    hop_count=len(path_edges),
                    path_edge_types=path_edges,
                    path_node_ids=path_nodes,
                )
            )
        else:
            entries.append(
                AuditEntry(
                    node_id=node.node_id,
                    accession=accession,
                    node_kind=kind,
                    reachable=False,
                )
            )

    actual_size = len(entries) or 1
    pass_rate = reachable_count / actual_size
    return ReachabilityAuditReport(
        snapshot_id=snapshot.snapshot_id,
        issuer_id=snapshot.issuer_id,
        hop_budget=hop,
        sample_size=len(entries),
        pass_rate=pass_rate,
        pass_threshold=threshold,
        audit_ready=pass_rate >= threshold,
        structural_edge_types=STRUCTURAL_EDGE_TYPE_VALUES,
        entries=entries,
        builder_version=snapshot.manifest.graph_builder_version or DOCLING_GRAPH_MAPPER_VERSION,
    )


def save_reachability_report(report: ReachabilityAuditReport, base_dir: Path) -> Path:
    path = base_dir / report.issuer_id / f"{report.snapshot_id}.reachability.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2))
    return path
