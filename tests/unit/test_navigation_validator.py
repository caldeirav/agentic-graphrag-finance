"""Unit tests for navigation hop validator (009)."""

from __future__ import annotations

import os

import pytest

from graph.legacy_builder import build_snapshot as legacy_build_snapshot
from models.enums import GraphEdgeType, GraphNodeType
from models.filing import FilingRef
from models.graph import GraphEdge, GraphNode
from models.filing import SectionBlock
from models.parsing import ParsedDocument
from retrieval.navigation.budget import load_navigation_budget
from retrieval.navigation.models import HopCandidate, HopDirection, HopProposal, NavigationStage
from retrieval.navigation.validator import validate_hop_proposal


def _mini_snapshot():
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
        sections=[
            SectionBlock(section_id="mda", title="MD&A Risk Factors", text="risk " * 20, level=1),
        ],
        tables=[],
        footnotes=[],
        parse_confidence=1.0,
        parser_version="t",
        content_hash="h",
    )
    return legacy_build_snapshot("0000320193", [doc], snapshot_id="nav-unit")


def test_validator_approves_contains_hop():
    snap = _mini_snapshot()
    doc_id = "doc-0000320193-24-000123"
    sec_id = f"{doc_id}-mda"
    proposal = HopProposal(
        stage=NavigationStage.MESO,
        source_node_id=doc_id,
        candidates=[
            HopCandidate(
                target_node_id=sec_id,
                edge_type=GraphEdgeType.CONTAINS,
                direction=HopDirection.OUTGOING,
                score=1.0,
            )
        ],
    )
    result = validate_hop_proposal(
        proposal=proposal,
        snapshot=snap,
        filing_accessions={"0000320193-24-000123"},
        budgets=load_navigation_budget(),
        scope_key="0000320193-24-000123",
    )
    assert result.status == "approved"
    assert result.approved_hop is not None


def test_validator_rejects_disallowed_edge():
    snap = _mini_snapshot()
    doc_id = "doc-0000320193-24-000123"
    snap.edges.append(
        GraphEdge(
            edge_id="e-temp",
            source_id=doc_id,
            target_id="doc-other",
            edge_type=GraphEdgeType.TEMPORAL_TRANSITION,
        )
    )
    proposal = HopProposal(
        stage=NavigationStage.MESO,
        source_node_id=doc_id,
        candidates=[
            HopCandidate(
                target_node_id="doc-other",
                edge_type=GraphEdgeType.TEMPORAL_TRANSITION,
                direction=HopDirection.OUTGOING,
            )
        ],
    )
    result = validate_hop_proposal(
        proposal=proposal,
        snapshot=snap,
        filing_accessions={"0000320193-24-000123"},
        budgets=load_navigation_budget(),
        scope_key="0000320193-24-000123",
    )
    assert result.status == "rejected"
    assert result.rejection_code in ("disallowed_edge", "no_valid_candidate", "edge_not_found")


def test_validator_rejects_out_of_scope_accession():
    snap = _mini_snapshot()
    other = GraphNode(
        node_id="doc-000032019325000079",
        node_type=GraphNodeType.DOCUMENT,
        label="other",
        properties={},
    )
    snap.nodes.append(other)
    snap.edges.append(
        GraphEdge(
            edge_id="e-bad",
            source_id="doc-000032019324000123",
            target_id=other.node_id,
            edge_type=GraphEdgeType.REFERENCES,
        )
    )
    proposal = HopProposal(
        stage=NavigationStage.MESO,
        source_node_id="doc-0000320193-24-000123",
        candidates=[
            HopCandidate(
                target_node_id=other.node_id,
                edge_type=GraphEdgeType.REFERENCES,
                direction=HopDirection.OUTGOING,
            )
        ],
    )
    result = validate_hop_proposal(
        proposal=proposal,
        snapshot=snap,
        filing_accessions={"0000320193-24-000123"},
        budgets=load_navigation_budget(),
        scope_key="0000320193-24-000123",
    )
    assert result.status == "rejected"


@pytest.mark.parametrize("code", ["budget_exceeded"])
def test_validator_budget_exhausted(code: str):
    snap = _mini_snapshot()
    budgets = load_navigation_budget()
    budgets.limits.query_max_total_visits = 0
    proposal = HopProposal(
        stage=NavigationStage.MESO,
        source_node_id="doc-0000320193-24-000123",
        candidates=[],
    )
    result = validate_hop_proposal(
        proposal=proposal,
        snapshot=snap,
        filing_accessions={"0000320193-24-000123"},
        budgets=budgets,
        scope_key="0000320193-24-000123",
    )
    assert result.status == "rejected"
    assert result.rejection_code == code
