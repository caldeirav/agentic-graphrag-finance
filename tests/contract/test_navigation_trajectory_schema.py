"""Contract: navigation_trace.json schema (009)."""

from __future__ import annotations

from retrieval.navigation.models import NavigationTraceRecord


def test_navigation_trace_record_roundtrip():
    rec = NavigationTraceRecord(
        meso_ranks=[],
        visit_counts={"meso": 1, "micro": 2, "total": 3},
        scan_ratio=0.1,
        structural_edge_types_used=["CONTAINS"],
    )
    data = rec.to_trajectory_dict()
    assert "visit_counts" in data
    assert "scan_ratio" in data
    assert "structural_edge_types_used" in data
    assert "meso_ranks" in data
    assert "micro_paths" in data
