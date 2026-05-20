"""Reachability audit report schema."""

from datetime import UTC, datetime

from models.graph_audit import AuditEntry, ReachabilityAuditReport


def test_reachability_report_required_fields():
    report = ReachabilityAuditReport(
        snapshot_id="sid",
        issuer_id="AAPL",
        hop_budget=6,
        sample_size=100,
        pass_rate=0.96,
        pass_threshold=0.95,
        audit_ready=True,
        structural_edge_types=["CONTAINS", "NEXT"],
        entries=[
            AuditEntry(
                node_id="doc-0000320193-24-000123-xbrl-abc",
                accession="0000320193-24-000123",
                node_kind="xbrl_fact",
                reachable=True,
                hop_count=3,
                path_edge_types=["CONTAINS", "CONTAINS", "CONTAINS"],
                path_node_ids=["doc-0000320193-24-000123", "doc-0000320193-24-000123-xbrl-facts", "n3"],
            )
        ],
        created_at=datetime.now(UTC),
        builder_version="docling-graph-mapper-1.0.0",
    )
    data = report.model_dump()
    assert data["audit_ready"] is True
    assert data["hop_budget"] == 6
    assert data["entries"][0]["node_kind"] == "xbrl_fact"
