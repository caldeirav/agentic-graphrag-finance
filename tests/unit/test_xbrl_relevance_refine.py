"""Tests for XBRL relevance label refinement."""

from __future__ import annotations

from datetime import date, datetime, UTC

from models.enums import GraphEdgeType, GraphNodeType
from models.filing import FilingRef
from models.graph import GraphEdge, GraphManifest, GraphNode, GraphSnapshot

from evaluation.reproduction.relevance import refine_xbrl_relevance_chunks


def _xbrl_node(node_id: str, concept: str, excerpt: str) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=GraphNodeType.CHUNK_XBRL_FACT,
        label=concept,
        source_ref=excerpt,
        properties={"xbrl_concept": concept},
    )


def test_refine_xbrl_to_concept_matched_subset() -> None:
    section = GraphNode(
        node_id="sec-xbrl",
        node_type=GraphNodeType.SECTION,
        label="XBRL",
        properties={"narrative_kind": "xbrl_bucket"},
    )
    revenue = _xbrl_node(
        "xbrl-rev",
        "RevenuesNetOfInterestExpense",
        "XBRL RevenuesNetOfInterestExpense: $100.00 million for period 2025-12-31",
    )
    other = _xbrl_node(
        "xbrl-other",
        "EntityCommonStockSharesOutstanding",
        "XBRL EntityCommonStockSharesOutstanding: $50.00 million shares",
    )
    snap = GraphSnapshot(
        snapshot_id="snap-1",
        issuer_id="XOM",
        nodes=[section, revenue, other],
        edges=[
            GraphEdge(
                edge_id="e1",
                source_id="sec-xbrl",
                target_id="xbrl-rev",
                edge_type=GraphEdgeType.CONTAINS,
            ),
            GraphEdge(
                edge_id="e2",
                source_id="sec-xbrl",
                target_id="xbrl-other",
                edge_type=GraphEdgeType.CONTAINS,
            ),
        ],
        manifest=GraphManifest(
            created_at=datetime.now(UTC),
            filing_refs=[
                FilingRef(
                    cik="0000034088",
                    accession="0000034088-26-000067",
                    form_type="10-K",
                    filed_at=date(2026, 2, 1),
                    period_end=date(2025, 12, 31),
                    source_uri="",
                )
            ],
            parser_version="test",
            graph_builder_version="test",
            storage_path=".",
        ),
    )
    refined = refine_xbrl_relevance_chunks(
        snap,
        ["xbrl-rev", "xbrl-other"],
        question="What was total revenue in 2025?",
        gt_answer="100000000",
    )
    assert refined == ["xbrl-rev"]
