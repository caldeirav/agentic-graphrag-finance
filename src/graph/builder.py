"""Build GraphSnapshot from ParsedDocument(s) via docling-graph mapper."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

from graph.docling_graph_mapper import DOCLING_GRAPH_MAPPER_VERSION, map_filing
from graph.similarity import add_deterministic_concept_edges, add_thematic_edges, load_similarity_config
from models.enums import GraphEdgeType
from models.graph import GraphEdge, GraphManifest, GraphSnapshot
from models.graph_audit import FilingMaterializationStatus
from models.parsing import ParsedDocument

GRAPH_BUILDER_VERSION = DOCLING_GRAPH_MAPPER_VERSION


def build_snapshot(
    issuer_id: str,
    documents: list[ParsedDocument],
    *,
    snapshot_id: str | None = None,
) -> GraphSnapshot:
    """Materialize issuer snapshot; excludes fail-closed filings."""
    if os.environ.get("GRAPH_BUILDER", "docling-graph").strip().lower() == "legacy":
        from graph.legacy_builder import build_snapshot as legacy_build

        return legacy_build(issuer_id, documents, snapshot_id=snapshot_id)

    sid = snapshot_id or str(uuid.uuid4())
    nodes = []
    edges: list[GraphEdge] = []
    edge_idx = 0
    included_docs: list[ParsedDocument] = []

    for doc in documents:
        filing_nodes, filing_edges, result, edge_idx = map_filing(doc, edge_idx_start=edge_idx)
        if result.status == FilingMaterializationStatus.FAILED:
            continue
        included_docs.append(doc)
        nodes.extend(filing_nodes)
        edges.extend(filing_edges)

    sorted_docs = sorted(included_docs, key=lambda d: d.filing.period_end)
    for i in range(1, len(sorted_docs)):
        prev_doc = f"doc-{sorted_docs[i - 1].filing.accession}"
        curr_doc = f"doc-{sorted_docs[i].filing.accession}"
        edges.append(
            GraphEdge(
                edge_id=f"e-{edge_idx}",
                source_id=prev_doc,
                target_id=curr_doc,
                edge_type=GraphEdgeType.TEMPORAL_TRANSITION,
                properties={
                    "period_from": str(sorted_docs[i - 1].filing.period_end),
                    "period_to": str(sorted_docs[i].filing.period_end),
                },
            )
        )
        edge_idx += 1

    snapshot = GraphSnapshot(
        snapshot_id=sid,
        issuer_id=issuer_id,
        nodes=nodes,
        edges=edges,
        manifest=GraphManifest(
            created_at=datetime.now(UTC),
            filing_refs=[d.filing for d in included_docs],
            parser_version=included_docs[0].parser_version if included_docs else "",
            graph_builder_version=GRAPH_BUILDER_VERSION,
            storage_path="",
            node_count=len(nodes),
            edge_count=len(edges),
        ),
    )

    sim_cfg = load_similarity_config()
    if sim_cfg.get("deterministic_enabled", True):
        add_deterministic_concept_edges(snapshot)
    add_thematic_edges(snapshot, sim_cfg)
    snapshot.manifest.edge_count = len(snapshot.edges)
    return snapshot
