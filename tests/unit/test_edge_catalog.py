"""Edge catalog audit whitelist."""

from graph.edge_catalog import AUDIT_EDGE_TYPES, STRUCTURAL_EDGE_TYPES
from models.enums import GraphEdgeType


def test_audit_whitelist_excludes_cross_filing_edges():
    assert GraphEdgeType.TEMPORAL_TRANSITION not in AUDIT_EDGE_TYPES
    assert GraphEdgeType.SEMANTIC_SIMILARITY not in AUDIT_EDGE_TYPES
    assert GraphEdgeType.CONTAINS in STRUCTURAL_EDGE_TYPES
