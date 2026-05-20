"""Map ParsedDocument → GraphNode/GraphEdge via docling-graph schema contract.

Bridge layer: structural hierarchy normalized from Docling parse output; optional
``docling_graph.GraphConverter`` integration when a Docling document is available.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from graph.edge_catalog import STRUCTURAL_EDGE_TYPES
from models.enums import GraphEdgeType, GraphNodeType
from models.graph import GraphEdge, GraphNode
from models.graph_audit import FilingMaterializationResult, FilingMaterializationStatus
from models.parsing import ParsedDocument
from parsing.xbrl_facts import consolidate_xbrl_fact_rows, fact_to_excerpt

DOCLING_GRAPH_MAPPER_VERSION = "docling-graph-mapper-1.0.0"

_NUMERIC_CELL = re.compile(r"[\d,]+\.?\d*")


def map_filing(
    doc: ParsedDocument,
    *,
    edge_idx_start: int = 0,
) -> tuple[list[GraphNode], list[GraphEdge], FilingMaterializationResult, int]:
    """Materialize one filing; fail-closed when mandatory structure is broken."""
    doc_id = f"doc-{doc.filing.accession}"
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    edge_idx = edge_idx_start
    unresolved_footnotes = 0
    unresolved_cross_refs = 0
    footnote_ids: dict[str, str] = {}

    has_xbrl_tables = any(t.table_id.startswith("xbrl-facts") for t in doc.tables)
    if not doc.sections and not has_xbrl_tables:
        return (
            nodes,
            edges,
            FilingMaterializationResult(
                accession=doc.filing.accession,
                status=FilingMaterializationStatus.FAILED,
                failure_reason="zero sections and no XBRL facts under document",
            ),
            edge_idx,
        )

    nodes.append(
        GraphNode(
            node_id=doc_id,
            node_type=GraphNodeType.DOCUMENT,
            label=f"{doc.filing.form_type} {doc.filing.accession}",
            properties={
                "form_type": doc.filing.form_type,
                "period_end": str(doc.filing.period_end),
                "accession": doc.filing.accession,
            },
            source_ref=doc.content_hash,
        )
    )

    xbrl_section_id = f"{doc_id}-xbrl-facts"
    has_xbrl_section = False
    prev_section_id: str | None = None
    footnote_node_ids: set[str] = set()

    for fn in doc.footnotes:
        fn_id = f"{doc_id}-{fn.footnote_id}"
        footnote_ids[fn.footnote_id] = fn_id
        footnote_node_ids.add(fn_id)
        nodes.append(
            GraphNode(
                node_id=fn_id,
                node_type=GraphNodeType.CHUNK_PARAGRAPH,
                label=fn.footnote_id,
                properties={"footnote": True},
                source_ref=fn.text[:500],
            )
        )

    for sec in doc.sections:
        sec_id = f"{doc_id}-{sec.section_id}"
        nodes.append(
            GraphNode(
                node_id=sec_id,
                node_type=GraphNodeType.SECTION,
                label=sec.title,
                properties={"level": sec.level, "section_id": sec.section_id},
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

        if sec.parent_section_id:
            parent_id = f"{doc_id}-{sec.parent_section_id}"
            if any(n.node_id == parent_id for n in nodes):
                edges.append(
                    GraphEdge(
                        edge_id=f"e-{edge_idx}",
                        source_id=sec_id,
                        target_id=parent_id,
                        edge_type=GraphEdgeType.REFERENCES,
                        properties={"ref_type": "parent_section"},
                    )
                )
                edge_idx += 1
            else:
                unresolved_cross_refs += 1

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
                        properties={"level": 0, "xbrl": True},
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
            for concept, fields in facts:
                if "value" not in fields:
                    continue
                excerpt = fact_to_excerpt(concept, fields)
                period_key = fields.get("period", "")
                h = hashlib.sha256(f"{concept}|{period_key}".encode()).hexdigest()[:12]
                fact_id = f"{doc_id}-xbrl-{h}"
                nodes.append(
                    GraphNode(
                        node_id=fact_id,
                        node_type=GraphNodeType.CHUNK_XBRL_FACT,
                        label=concept[:80],
                        properties={
                            "xbrl_concept": concept,
                            "period": period_key,
                            "currency": fields.get("currency", ""),
                        },
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

        for ri, row in enumerate(table.rows):
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

        for fn_ref in table.footnote_ids:
            fn_node_id = f"{doc_id}-{fn_ref}"
            if fn_node_id in footnote_node_ids:
                edges.append(
                    GraphEdge(
                        edge_id=f"e-{edge_idx}",
                        source_id=chunk_id,
                        target_id=fn_node_id,
                        edge_type=GraphEdgeType.FOOTNOTE_OF,
                        properties={"ref_id": fn_ref},
                    )
                )
                edge_idx += 1
            else:
                unresolved_footnotes += 1

    for fn in doc.footnotes:
        fn_id = f"{doc_id}-{fn.footnote_id}"
        if fn.parent_table_id:
            parent_table = f"{doc_id}-{fn.parent_table_id}"
            if any(n.node_id == parent_table for n in nodes):
                edges.append(
                    GraphEdge(
                        edge_id=f"e-{edge_idx}",
                        source_id=parent_table,
                        target_id=fn_id,
                        edge_type=GraphEdgeType.FOOTNOTE_OF,
                        properties={"ref_id": fn.footnote_id},
                    )
                )
                edge_idx += 1
            else:
                edges.append(
                    GraphEdge(
                        edge_id=f"e-{edge_idx}",
                        source_id=doc_id,
                        target_id=fn_id,
                        edge_type=GraphEdgeType.CONTAINS,
                    )
                )
                edge_idx += 1
        else:
            edges.append(
                GraphEdge(
                    edge_id=f"e-{edge_idx}",
                    source_id=doc_id,
                    target_id=fn_id,
                    edge_type=GraphEdgeType.CONTAINS,
                )
            )
            edge_idx += 1

    orphans = _orphan_evidence_nodes(nodes, edges, doc_id)
    if orphans:
        return (
            nodes,
            edges,
            FilingMaterializationResult(
                accession=doc.filing.accession,
                status=FilingMaterializationStatus.FAILED,
                failure_reason=f"orphan evidence nodes: {orphans[:3]}",
                node_count=len(nodes),
                edge_count=len(edges),
                unresolved_footnotes=unresolved_footnotes,
                unresolved_cross_refs=unresolved_cross_refs,
            ),
            edge_idx,
        )

    return (
        nodes,
        edges,
        FilingMaterializationResult(
            accession=doc.filing.accession,
            status=FilingMaterializationStatus.INCLUDED,
            node_count=len(nodes),
            edge_count=len(edges),
            unresolved_footnotes=unresolved_footnotes,
            unresolved_cross_refs=unresolved_cross_refs,
        ),
        edge_idx,
    )


def _orphan_evidence_nodes(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    doc_id: str,
) -> list[str]:
    """Evidence chunks without a CONTAINS path to the document root."""
    evidence_types = {
        GraphNodeType.CHUNK_TABLE,
        GraphNodeType.CHUNK_ROW,
        GraphNodeType.CHUNK_PARAGRAPH,
        GraphNodeType.CHUNK_XBRL_FACT,
    }
    contains_parent: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.edge_type == GraphEdgeType.CONTAINS:
            contains_parent[edge.target_id].add(edge.source_id)

    orphans: list[str] = []
    for node in nodes:
        if node.node_type not in evidence_types:
            continue
        if not _reachable_via_contains(node.node_id, doc_id, contains_parent):
            orphans.append(node.node_id)
    return orphans


def _reachable_via_contains(
    node_id: str,
    doc_id: str,
    contains_parent: dict[str, set[str]],
) -> bool:
    seen: set[str] = set()
    stack = [node_id]
    while stack:
        current = stack.pop()
        if current == doc_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        for parent in contains_parent.get(current, ()):
            stack.append(parent)
    return False


def validate_catalog_edges(edges: list[GraphEdge]) -> None:
    """Assert all edges use catalog types (development guard)."""
    allowed = STRUCTURAL_EDGE_TYPES | {
        GraphEdgeType.TEMPORAL_TRANSITION,
        GraphEdgeType.SEMANTIC_SIMILARITY,
    }
    for edge in edges:
        if edge.edge_type not in allowed:
            raise ValueError(f"off-catalog edge type: {edge.edge_type}")
