"""Unit tests for filing-level XBRL catalog index (023 M3b)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from graph.query_api import InMemoryGraphQueryAPI
from models.enums import EvidenceSourceType, GraphEdgeType, GraphNodeType
from models.filing import FilingRef
from models.graph import GraphEdge, GraphManifest, GraphNode, GraphSnapshot
from models.query import EvidenceChunk
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.xbrl_graph_chunks import collect_filing_xbrl_chunks, collect_filing_xbrl_taxonomy_lookup
from retrieval.skills.xbrl_taxonomy_catalog import build_taxonomy_catalog

ACCESSION = "0000320193-25-000123"
DOC = f"doc-{ACCESSION}"


def _snapshot(extra_nodes: list[GraphNode] | None = None) -> GraphSnapshot:
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
            label="Net income (loss)",
            properties={
                "xbrl_concept": "NetIncomeLoss",
                "xbrl_standard_label": "Net income (loss)",
                "xbrl_metric_roles": "net_income,margin_numerator",
                "xbrl_statement_role": "income_statement",
            },
            source_ref="XBRL NetIncomeLoss: $36.00 billion USD for period 2025-01-01 - 2025-12-31",
        ),
        GraphNode(
            node_id=f"{DOC}-xbrl-rev",
            node_type=GraphNodeType.CHUNK_XBRL_FACT,
            label="Revenues",
            properties={"xbrl_concept": "Revenues"},
            source_ref="XBRL Revenues: $413.00 billion USD for period 2025-01-01 - 2025-12-31",
        ),
        GraphNode(
            node_id=f"{DOC}-xbrl-pretax",
            node_type=GraphNodeType.CHUNK_XBRL_FACT,
            label="Pretax",
            properties={"xbrl_concept": "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"},
            source_ref=(
                "XBRL IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest: "
                "$40.00 billion USD for period 2025-01-01 - 2025-12-31"
            ),
        ),
    ]
    if extra_nodes:
        nodes.extend(extra_nodes)
    edges = [
        GraphEdge(edge_id="e1", source_id=DOC, target_id=f"{DOC}-xbrl-ni", edge_type=GraphEdgeType.CONTAINS),
        GraphEdge(edge_id="e2", source_id=DOC, target_id=f"{DOC}-xbrl-rev", edge_type=GraphEdgeType.CONTAINS),
        GraphEdge(edge_id="e3", source_id=DOC, target_id=f"{DOC}-xbrl-pretax", edge_type=GraphEdgeType.CONTAINS),
    ]
    filing = FilingRef(
        cik="0000320193",
        accession=ACCESSION,
        form_type="10-K",
        filed_at=date(2025, 11, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    return GraphSnapshot(
        snapshot_id="snap-filing-index",
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


def test_collect_filing_xbrl_chunks_returns_bound_accession_nodes() -> None:
    snap = _snapshot()
    api = InMemoryGraphQueryAPI(snap)
    filing = snap.manifest.filing_refs[0]
    chunks = collect_filing_xbrl_chunks(api, snap.snapshot_id, [filing])
    assert len(chunks) == 3
    concepts = {c.excerpt.split()[1] for c in chunks if c.excerpt.startswith("XBRL")}
    assert "NetIncomeLoss:" in concepts or any("NetIncomeLoss" in c.excerpt for c in chunks)


def test_build_taxonomy_catalog_includes_filing_index_without_micro_evidence() -> None:
    snap = _snapshot()
    api = InMemoryGraphQueryAPI(snap)
    filing = snap.manifest.filing_refs[0]
    intent = MetricIntent(metric_type="ratio", metric_label="Net profit margin", periods_needed=1)
    query = "What was net profit margin for fiscal year 2025?"
    catalog = build_taxonomy_catalog(
        [],
        query,
        [filing],
        metric_intent=intent,
        graph_api=api,
        snapshot_id=snap.snapshot_id,
    )
    concepts = {entry.concept for entry in catalog.entries}
    assert "Revenues" in concepts
    assert any("NetIncome" in c or c == "ProfitLoss" for c in concepts)


def test_margin_catalog_prefers_net_income_over_pretax_in_trimmed_set() -> None:
    snap = _snapshot()
    api = InMemoryGraphQueryAPI(snap)
    filing = snap.manifest.filing_refs[0]
    micro = EvidenceChunk(
        chunk_node_id=f"{DOC}-xbrl-rev",
        excerpt="XBRL Revenues: $413.00 billion USD for period 2025-01-01 - 2025-12-31",
        content_hash="h",
        citation_label="XBRL",
        source_type=EvidenceSourceType.XBRL,
        accession=ACCESSION,
    )
    intent = MetricIntent(metric_type="ratio", metric_label="Net profit margin", periods_needed=1)
    query = "What was net profit margin for fiscal year 2025?"
    catalog = build_taxonomy_catalog(
        [micro],
        query,
        [filing],
        metric_intent=intent,
        graph_api=api,
        snapshot_id=snap.snapshot_id,
    )
    income_rows = [e for e in catalog.entries if "net_income" in e.metric_roles]
    assert income_rows
    assert income_rows[0].concept == "NetIncomeLoss"


def test_taxonomy_lookup_from_graph_properties_enriches_catalog() -> None:
    snap = _snapshot()
    api = InMemoryGraphQueryAPI(snap)
    filing = snap.manifest.filing_refs[0]
    lookup = collect_filing_xbrl_taxonomy_lookup(api, snap.snapshot_id, [filing])
    assert lookup["NetIncomeLoss"].standard_label == "Net income (loss)"
    catalog = build_taxonomy_catalog(
        [],
        "Net profit margin FY2025",
        [filing],
        metric_intent=MetricIntent(metric_type="ratio", metric_label="Net profit margin", periods_needed=1),
        graph_api=api,
        snapshot_id=snap.snapshot_id,
    )
    ni = next(e for e in catalog.entries if e.concept == "NetIncomeLoss")
    assert ni.standard_label == "Net income (loss)"
    assert "net_income" in ni.metric_roles
