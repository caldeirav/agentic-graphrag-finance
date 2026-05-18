"""Persist and load GraphSnapshot as GraphML + manifest."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from models.enums import GraphEdgeType, GraphNodeType
from models.graph import GraphEdge, GraphNode, GraphSnapshot


def _to_nx(snapshot: GraphSnapshot) -> nx.DiGraph:
    g = nx.DiGraph()
    for node in snapshot.nodes:
        g.add_node(
            node.node_id,
            node_type=node.node_type.value,
            label=node.label,
            source_ref=node.source_ref,
            **{f"prop_{k}": v for k, v in node.properties.items()},
        )
    for edge in snapshot.edges:
        g.add_edge(
            edge.source_id,
            edge.target_id,
            edge_type=edge.edge_type.value,
            edge_id=edge.edge_id,
        )
    return g


def _from_nx(snapshot_id: str, issuer_id: str, g: nx.DiGraph, manifest_path: Path) -> GraphSnapshot:
    from models.graph import GraphManifest

    manifest_data = json.loads(manifest_path.read_text())
    manifest = GraphManifest.model_validate(manifest_data)
    nodes = []
    for nid, data in g.nodes(data=True):
        props = {k[5:]: v for k, v in data.items() if k.startswith("prop_")}
        nodes.append(
            GraphNode(
                node_id=nid,
                node_type=GraphNodeType(data["node_type"]),
                label=data.get("label", ""),
                source_ref=data.get("source_ref", ""),
                properties=props,
            )
        )
    edges = []
    for u, v, data in g.edges(data=True):
        edges.append(
            GraphEdge(
                edge_id=str(data.get("edge_id", f"{u}->{v}")),
                source_id=u,
                target_id=v,
                edge_type=GraphEdgeType(data["edge_type"]),
            )
        )
    return GraphSnapshot(
        snapshot_id=snapshot_id,
        issuer_id=issuer_id,
        nodes=nodes,
        edges=edges,
        manifest=manifest,
    )


def save_snapshot(snapshot: GraphSnapshot, base_dir: Path) -> Path:
    issuer_dir = base_dir / snapshot.issuer_id
    issuer_dir.mkdir(parents=True, exist_ok=True)
    graph_path = issuer_dir / f"{snapshot.snapshot_id}.graphml"
    manifest_path = issuer_dir / f"{snapshot.snapshot_id}.manifest.json"
    nx.write_graphml(_to_nx(snapshot), graph_path)
    manifest_path.write_text(snapshot.manifest.model_dump_json(indent=2))
    return graph_path


def load_snapshot(issuer_id: str, snapshot_id: str, base_dir: Path) -> GraphSnapshot:
    issuer_dir = base_dir / issuer_id
    graph_path = issuer_dir / f"{snapshot_id}.graphml"
    manifest_path = issuer_dir / f"{snapshot_id}.manifest.json"
    g = nx.read_graphml(graph_path)
    return _from_nx(snapshot_id, issuer_id, g, manifest_path)
