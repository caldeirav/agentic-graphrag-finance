"""Scope and disallowed-edge tests for navigation validator."""

from __future__ import annotations

from graph.legacy_builder import build_snapshot as legacy_build_snapshot
from models.enums import GraphEdgeType
from models.filing import FilingRef, SectionBlock
from models.graph import GraphEdge
from models.parsing import ParsedDocument
from retrieval.navigation.budget import load_navigation_budget
from retrieval.navigation.models import HopCandidate, HopDirection, HopProposal, NavigationStage
from retrieval.navigation.validator import validate_hop_proposal


def _snap():
    ref = FilingRef(
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=__import__("datetime").date(2024, 9, 28),
        period_end=__import__("datetime").date(2024, 9, 28),
        source_uri="u",
    )
    doc = ParsedDocument(
        filing=ref,
        sections=[SectionBlock(section_id="a", title="A", text="text", level=1)],
        tables=[],
        footnotes=[],
        parse_confidence=1.0,
        parser_version="t",
        content_hash="h",
    )
    return legacy_build_snapshot("0000320193", [doc], snapshot_id="scope")


def test_rejects_semantic_similarity_edge():
    snap = _snap()
    doc_id = "doc-0000320193-24-000123"
    snap.edges.append(
        GraphEdge(
            edge_id="e-sem",
            source_id=doc_id,
            target_id=f"{doc_id}-a",
            edge_type=GraphEdgeType.SEMANTIC_SIMILARITY,
        )
    )
    proposal = HopProposal(
        stage=NavigationStage.MICRO,
        source_node_id=doc_id,
        candidates=[
            HopCandidate(
                target_node_id=f"{doc_id}-a",
                edge_type=GraphEdgeType.SEMANTIC_SIMILARITY,
                direction=HopDirection.OUTGOING,
            )
        ],
    )
    result = validate_hop_proposal(
        proposal=proposal,
        snapshot=snap,
        filing_accessions={"0000320193-24-000123"},
        budgets=load_navigation_budget(),
        scope_key="s",
    )
    assert result.status == "rejected"
