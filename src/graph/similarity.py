"""Cross-filing semantic similarity edges (deterministic + optional thematic)."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from models.enums import GraphEdgeType, GraphNodeType
from models.graph import GraphEdge, GraphSnapshot

_RISK_THEME = re.compile(
    r"\b(risk|uncertainty|litigation|regulatory|supply chain|cyber|climate|"
    r"macroeconomic|inflation|interest rate|geopolitical)\b",
    re.I,
)


def load_similarity_config(path: Path | None = None) -> dict:
    cfg_path = path or Path("configs/graph_similarity.yaml")
    if not cfg_path.exists():
        return {"deterministic_enabled": True, "thematic_enabled": False, "thematic_threshold": 0.82}
    return yaml.safe_load(cfg_path.read_text()) or {}


def add_deterministic_concept_edges(snapshot: GraphSnapshot) -> int:
    """Link XBRL fact nodes sharing concept QName across different filings."""
    facts = [
        n
        for n in snapshot.nodes
        if n.node_type == GraphNodeType.CHUNK_XBRL_FACT
        and n.properties.get("xbrl_concept")
    ]
    by_concept: dict[str, list] = {}
    for node in facts:
        concept = str(node.properties["xbrl_concept"])
        by_concept.setdefault(concept, []).append(node)

    edge_idx = len(snapshot.edges)
    added = 0
    for concept, group in by_concept.items():
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            doc_a = _doc_id_from_node(a.node_id)
            for b in group[i + 1 :]:
                doc_b = _doc_id_from_node(b.node_id)
                if doc_a == doc_b:
                    continue
                snapshot.edges.append(
                    GraphEdge(
                        edge_id=f"e-sim-det-{edge_idx}",
                        source_id=a.node_id,
                        target_id=b.node_id,
                        edge_type=GraphEdgeType.SEMANTIC_SIMILARITY,
                        properties={
                            "link_method": "deterministic",
                            "concept_qname": concept,
                            "period_from": str(a.properties.get("period", "")),
                            "period_to": str(b.properties.get("period", "")),
                        },
                    )
                )
                edge_idx += 1
                added += 1
    return added


def add_thematic_edges(snapshot: GraphSnapshot, config: dict | None = None) -> int:
    """Optional narrative risk co-mention links (embedding-free keyword overlap v1)."""
    cfg = config or load_similarity_config()
    env_on = os.environ.get("USE_THEMATIC_GRAPH_LINKS", "").strip() in ("1", "true", "yes")
    if not (cfg.get("thematic_enabled") or env_on):
        return 0

    threshold = float(cfg.get("thematic_threshold", 0.82))
    max_edges = int(cfg.get("max_thematic_edges_per_snapshot", 500))
    paragraphs = [
        n
        for n in snapshot.nodes
        if n.node_type == GraphNodeType.CHUNK_PARAGRAPH
        and not n.properties.get("footnote")
        and _RISK_THEME.search(n.source_ref or n.label or "")
    ]
    if len(paragraphs) < 2:
        return 0

    edge_idx = len(snapshot.edges)
    added = 0
    for i, a in enumerate(paragraphs):
        if added >= max_edges:
            break
        themes_a = set(_RISK_THEME.findall(a.source_ref or a.label or ""))
        if not themes_a:
            continue
        for b in paragraphs[i + 1 :]:
            if added >= max_edges:
                break
            if _doc_id_from_node(a.node_id) == _doc_id_from_node(b.node_id):
                continue
            themes_b = set(_RISK_THEME.findall(b.source_ref or b.label or ""))
            if not themes_b:
                continue
            overlap = len(themes_a & themes_b) / max(len(themes_a | themes_b), 1)
            if overlap < threshold:
                continue
            snapshot.edges.append(
                GraphEdge(
                    edge_id=f"e-sim-th-{edge_idx}",
                    source_id=a.node_id,
                    target_id=b.node_id,
                    edge_type=GraphEdgeType.SEMANTIC_SIMILARITY,
                    properties={
                        "link_method": "thematic",
                        "similarity_score": round(overlap, 4),
                    },
                )
            )
            edge_idx += 1
            added += 1
    return added


def _doc_id_from_node(node_id: str) -> str:
    m = re.match(r"^(doc-\d{10}-\d{2}-\d{6})", node_id)
    if m:
        return m.group(1)
    return node_id
