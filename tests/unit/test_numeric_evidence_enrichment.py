"""Unit tests for numeric evidence enrichment (023 M2)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from graph.query_api import InMemoryGraphQueryAPI
from models.enums import EvidenceSourceType, GraphEdgeType, GraphNodeType
from models.filing import FilingRef
from models.graph import GraphEdge, GraphManifest, GraphNode, GraphSnapshot
from models.query import EvidenceChunk
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.numeric_evidence_enrichment import enrich_numeric_evidence

ACCESSION = "0000320193-25-000123"
DOC = f"doc-{ACCESSION}"


def _snapshot() -> GraphSnapshot:
    nodes = [
        GraphNode(
            node_id=DOC,
            node_type=GraphNodeType.DOCUMENT,
            label="10-K",
            properties={"accession": ACCESSION},
            source_ref="doc",
        ),
        GraphNode(
            node_id=f"{DOC}-xbrl-ni",
            node_type=GraphNodeType.CHUNK_XBRL_FACT,
            label="NetIncomeLoss",
            properties={"xbrl_concept": "NetIncomeLoss"},
            source_ref="XBRL NetIncomeLoss: $36.00 billion USD for period 2025-01-01 - 2025-12-31",
        ),
        GraphNode(
            node_id=f"{DOC}-xbrl-rev",
            node_type=GraphNodeType.CHUNK_XBRL_FACT,
            label="Revenues",
            properties={"xbrl_concept": "Revenues"},
            source_ref="XBRL Revenues: $413.00 billion USD for period 2025-01-01 - 2025-12-31",
        ),
    ]
    edges = [
        GraphEdge(
            edge_id="e1",
            source_id=DOC,
            target_id=f"{DOC}-xbrl-ni",
            edge_type=GraphEdgeType.CONTAINS,
        ),
        GraphEdge(
            edge_id="e2",
            source_id=DOC,
            target_id=f"{DOC}-xbrl-rev",
            edge_type=GraphEdgeType.CONTAINS,
        ),
    ]
    filing = _filing()
    return GraphSnapshot(
        snapshot_id="snap-enrich",
        issuer_id="0000320193",
        nodes=nodes,
        edges=edges,
        manifest=GraphManifest(
            created_at=datetime.now(UTC),
            filing_refs=[filing],
            parser_version="test",
            graph_builder_version="test",
            storage_path=".",
        ),
    )


def _filing() -> FilingRef:
    return FilingRef(
        cik="0000320193",
        accession=ACCESSION,
        form_type="10-K",
        filed_at=date(2025, 11, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )


def test_enrichment_adds_missing_revenue_for_margin_query() -> None:
    snap = _snapshot()
    api = InMemoryGraphQueryAPI(snap)
    evidence = [
        EvidenceChunk(
            chunk_node_id=f"{DOC}-xbrl-ni",
            excerpt="XBRL NetIncomeLoss: $36.00 billion USD for period 2025-01-01 - 2025-12-31",
            content_hash="h1",
            source_type=EvidenceSourceType.XBRL,
            accession=ACCESSION,
            section_id="XBRL",
        )
    ]
    intent = MetricIntent(metric_type="ratio", metric_label="Net profit margin FY2025", periods_needed=1)
    result = enrich_numeric_evidence(
        evidence,
        "What was net profit margin for fiscal year 2025?",
        [_filing()],
        snapshot_id=snap.snapshot_id,
        graph_api=api,
        metric_intent=intent,
    )
    ids = {c.chunk_node_id for c in result.evidence}
    assert f"{DOC}-xbrl-rev" in ids
    assert f"{DOC}-xbrl-ni" in ids
    assert f"{DOC}-xbrl-rev" in result.added_chunk_ids


def test_enrichment_noop_when_both_families_present() -> None:
    snap = _snapshot()
    api = InMemoryGraphQueryAPI(snap)
    evidence = [
        EvidenceChunk(
            chunk_node_id=f"{DOC}-xbrl-ni",
            excerpt="XBRL NetIncomeLoss: $36.00 billion USD for period 2025-01-01 - 2025-12-31",
            content_hash="h1",
            source_type=EvidenceSourceType.XBRL,
            accession=ACCESSION,
            section_id="XBRL",
        ),
        EvidenceChunk(
            chunk_node_id=f"{DOC}-xbrl-rev",
            excerpt="XBRL Revenues: $413.00 billion USD for period 2025-01-01 - 2025-12-31",
            content_hash="h2",
            source_type=EvidenceSourceType.XBRL,
            accession=ACCESSION,
            section_id="XBRL",
        ),
    ]
    intent = MetricIntent(metric_type="ratio", metric_label="margin", periods_needed=1)
    result = enrich_numeric_evidence(
        evidence,
        "Net profit margin fiscal year 2025",
        [_filing()],
        snapshot_id=snap.snapshot_id,
        graph_api=api,
        metric_intent=intent,
    )
    assert result.added_chunk_ids == []
    assert len(result.evidence) == 2


def test_enrichment_yields_two_ratio_catalog_entries() -> None:
    from retrieval.skills.xbrl_fact_catalog import build_xbrl_fact_catalog

    snap = _snapshot()
    api = InMemoryGraphQueryAPI(snap)
    evidence = [
        EvidenceChunk(
            chunk_node_id=f"{DOC}-xbrl-ni",
            excerpt="XBRL NetIncomeLoss: $36.00 billion USD for period 2025-01-01 - 2025-12-31",
            content_hash="h1",
            source_type=EvidenceSourceType.XBRL,
            accession=ACCESSION,
            section_id="XBRL",
        )
    ]
    intent = MetricIntent(metric_type="ratio", metric_label="margin", periods_needed=1)
    enriched = enrich_numeric_evidence(
        evidence,
        "Net profit margin fiscal year 2025",
        [_filing()],
        snapshot_id=snap.snapshot_id,
        graph_api=api,
        metric_intent=intent,
    )
    catalog = build_xbrl_fact_catalog(
        enriched.evidence,
        "Net profit margin fiscal year 2025",
        [_filing()],
        metric_intent=intent,
    )
    concepts = {entry.concept for entry in catalog}
    assert len(catalog) >= 2
    assert any("NetIncome" in c for c in concepts)
    assert any("Revenue" in c for c in concepts)
