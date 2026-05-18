"""Build GraphSnapshot from ParsedDocument(s)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from models.enums import GraphEdgeType, GraphNodeType
from models.graph import GraphEdge, GraphManifest, GraphNode, GraphSnapshot
from models.parsing import ParsedDocument

GRAPH_BUILDER_VERSION = "docling-graph-mapper-0.1.0"


def build_snapshot(
    issuer_id: str,
    documents: list[ParsedDocument],
    *,
    snapshot_id: str | None = None,
) -> GraphSnapshot:
    sid = snapshot_id or str(uuid.uuid4())
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    edge_idx = 0

    doc_nodes: list[str] = []

    for doc in documents:
        doc_id = f"doc-{doc.filing.accession}"
        doc_nodes.append(doc_id)
        nodes.append(
            GraphNode(
                node_id=doc_id,
                node_type=GraphNodeType.DOCUMENT,
                label=f"{doc.filing.form_type} {doc.filing.accession}",
                properties={
                    "form_type": doc.filing.form_type,
                    "period_end": str(doc.filing.period_end),
                },
                source_ref=doc.content_hash,
            )
        )

        prev_section_id: str | None = None
        for sec in doc.sections:
            sec_id = f"{doc_id}-{sec.section_id}"
            nodes.append(
                GraphNode(
                    node_id=sec_id,
                    node_type=GraphNodeType.SECTION,
                    label=sec.title,
                    properties={"level": sec.level},
                    source_ref=sec.section_id,
                )
            )
            edges.append(
                GraphEdge(
                    edge_id=f"e-{edge_idx}",
                    source_id=doc_id,
                    target_id=sec_id,
                    edge_type=GraphEdgeType.CONTAINS,
                )
            )
            edge_idx += 1
            if prev_section_id:
                edges.append(
                    GraphEdge(
                        edge_id=f"e-{edge_idx}",
                        source_id=prev_section_id,
                        target_id=sec_id,
                        edge_type=GraphEdgeType.NEXT,
                    )
                )
                edge_idx += 1
            prev_section_id = sec_id

        for table in doc.tables:
            chunk_id = f"{doc_id}-{table.table_id}"
            nodes.append(
                GraphNode(
                    node_id=chunk_id,
                    node_type=GraphNodeType.CHUNK_TABLE,
                    label=table.table_id,
                    properties={"row_count": len(table.rows)},
                    source_ref=table.table_id,
                )
            )
            parent = prev_section_id or doc_id
            edges.append(
                GraphEdge(
                    edge_id=f"e-{edge_idx}",
                    source_id=parent,
                    target_id=chunk_id,
                    edge_type=GraphEdgeType.CONTAINS,
                )
            )
            edge_idx += 1
            for ri, row in enumerate(table.rows[:5]):
                row_id = f"{chunk_id}-row-{ri}"
                excerpt = " | ".join(row)
                nodes.append(
                    GraphNode(
                        node_id=row_id,
                        node_type=GraphNodeType.CHUNK_ROW,
                        label=excerpt[:80],
                        properties={},
                        source_ref=excerpt,
                    )
                )
                edges.append(
                    GraphEdge(
                        edge_id=f"e-{edge_idx}",
                        source_id=chunk_id,
                        target_id=row_id,
                        edge_type=GraphEdgeType.CONTAINS,
                    )
                )
                edge_idx += 1

        for fn in doc.footnotes:
            fn_id = f"{doc_id}-{fn.footnote_id}"
            nodes.append(
                GraphNode(
                    node_id=fn_id,
                    node_type=GraphNodeType.CHUNK_PARAGRAPH,
                    label=fn.footnote_id,
                    properties={},
                    source_ref=fn.text[:500],
                )
            )
            parent_table = f"{doc_id}-{fn.parent_table_id}" if fn.parent_table_id else doc_id
            edges.append(
                GraphEdge(
                    edge_id=f"e-{edge_idx}",
                    source_id=fn_id,
                    target_id=parent_table,
                    edge_type=GraphEdgeType.FOOTNOTE_OF,
                )
            )
            edge_idx += 1

    # Temporal transitions between documents (same issuer, ordered by period_end)
    sorted_docs = sorted(documents, key=lambda d: d.filing.period_end)
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

    manifest = GraphManifest(
        created_at=datetime.now(UTC),
        filing_refs=[d.filing for d in documents],
        parser_version=documents[0].parser_version if documents else "",
        graph_builder_version=GRAPH_BUILDER_VERSION,
        storage_path="",
        node_count=len(nodes),
        edge_count=len(edges),
    )
    return GraphSnapshot(
        snapshot_id=sid,
        issuer_id=issuer_id,
        nodes=nodes,
        edges=edges,
        manifest=manifest,
    )
