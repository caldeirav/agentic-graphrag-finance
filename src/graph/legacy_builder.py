"""Build GraphSnapshot from ParsedDocument(s)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from models.enums import GraphEdgeType, GraphNodeType
from models.graph import GraphEdge, GraphManifest, GraphNode, GraphSnapshot
from models.parsing import ParsedDocument
from graph.section_ontology import section_node_properties, xbrl_bucket_properties
from parsing.xbrl_facts import (
    consolidate_xbrl_fact_rows,
    fact_to_excerpt,
    select_facts_for_index,
)

GRAPH_BUILDER_VERSION = "docling-graph-mapper-0.2.0"


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

        xbrl_section_id = f"{doc_id}-xbrl-facts"
        has_xbrl_section = False

        prev_section_id: str | None = None
        for sec in doc.sections:
            sec_id = f"{doc_id}-{sec.section_id}"
            nodes.append(
                GraphNode(
                    node_id=sec_id,
                    node_type=GraphNodeType.SECTION,
                    label=sec.title,
                    properties=section_node_properties(sec),
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
            body = (sec.text or "").strip()
            if body and body != sec.title.strip() and len(body) > 40:
                para_id = f"{sec_id}-body"
                nodes.append(
                    GraphNode(
                        node_id=para_id,
                        node_type=GraphNodeType.CHUNK_PARAGRAPH,
                        label=sec.title[:80],
                        properties={"section_id": sec.section_id},
                        source_ref=body[:4000],
                    )
                )
                edges.append(
                    GraphEdge(
                        edge_id=f"e-{edge_idx}",
                        source_id=sec_id,
                        target_id=para_id,
                        edge_type=GraphEdgeType.CONTAINS,
                    )
                )
                edge_idx += 1

        for table in doc.tables:
            if table.table_id.startswith("xbrl-facts"):
                if not has_xbrl_section:
                    nodes.append(
                        GraphNode(
                            node_id=xbrl_section_id,
                            node_type=GraphNodeType.SECTION,
                            label="XBRL Financial Facts",
                            properties=xbrl_bucket_properties(),
                            source_ref="xbrl",
                        )
                    )
                    edges.append(
                        GraphEdge(
                            edge_id=f"e-{edge_idx}",
                            source_id=doc_id,
                            target_id=xbrl_section_id,
                            edge_type=GraphEdgeType.CONTAINS,
                        )
                    )
                    edge_idx += 1
                    has_xbrl_section = True

                facts = consolidate_xbrl_fact_rows(table.rows)
                for concept, fields in select_facts_for_index(facts):
                    excerpt = fact_to_excerpt(concept, fields)
                    period_key = fields.get("period", "")
                    h = hashlib.sha256(f"{concept}|{period_key}".encode()).hexdigest()[:12]
                    fact_id = f"{doc_id}-xbrl-{h}"
                    nodes.append(
                        GraphNode(
                            node_id=fact_id,
                            node_type=GraphNodeType.CHUNK_PARAGRAPH,
                            label=concept[:80],
                            properties={"xbrl_concept": concept},
                            source_ref=excerpt,
                        )
                    )
                    edges.append(
                        GraphEdge(
                            edge_id=f"e-{edge_idx}",
                            source_id=xbrl_section_id,
                            target_id=fact_id,
                            edge_type=GraphEdgeType.CONTAINS,
                        )
                    )
                    edge_idx += 1
                continue

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
            parent = xbrl_section_id if has_xbrl_section else (prev_section_id or doc_id)
            edges.append(
                GraphEdge(
                    edge_id=f"e-{edge_idx}",
                    source_id=parent,
                    target_id=chunk_id,
                    edge_type=GraphEdgeType.CONTAINS,
                )
            )
            edge_idx += 1
            for ri, row in enumerate(table.rows[:8]):
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
