"""Canonical graph edge types and traversal policy (004 edge catalog contract)."""

from __future__ import annotations

from models.enums import GraphEdgeType

STRUCTURAL_EDGE_TYPES: frozenset[GraphEdgeType] = frozenset(
    {
        GraphEdgeType.CONTAINS,
        GraphEdgeType.NEXT,
        GraphEdgeType.FOOTNOTE_OF,
        GraphEdgeType.REFERENCES,
    }
)

AUDIT_EDGE_TYPES: frozenset[GraphEdgeType] = STRUCTURAL_EDGE_TYPES

CROSS_FILING_EDGE_TYPES: frozenset[GraphEdgeType] = frozenset(
    {
        GraphEdgeType.TEMPORAL_TRANSITION,
        GraphEdgeType.SEMANTIC_SIMILARITY,
    }
)

# Agent meso/micro hops: structural only (009); cross-filing via macro binding per filing root.
AGENT_TRAVERSAL_POLICY: frozenset[GraphEdgeType] = STRUCTURAL_EDGE_TYPES

STRUCTURAL_EDGE_TYPE_VALUES: list[str] = [e.value for e in STRUCTURAL_EDGE_TYPES]
