"""Deterministic hop proposal validation (009)."""

from __future__ import annotations

from graph.accession import accession_from_node_id
from graph.edge_catalog import STRUCTURAL_EDGE_TYPES
from models.enums import GraphEdgeType, GraphNodeType
from models.graph import GraphSnapshot
from retrieval.navigation.budget import NavigationBudgetState
from retrieval.navigation.models import (
    HopDirection,
    HopProposal,
    HopValidationResult,
    NavigationVisit,
)


def _edge_exists(
    snapshot: GraphSnapshot,
    source_id: str,
    target_id: str,
    edge_type: GraphEdgeType,
    direction: HopDirection,
) -> bool:
    for edge in snapshot.edges:
        if edge.edge_type != edge_type:
            continue
        if direction == HopDirection.OUTGOING:
            if edge.source_id == source_id and edge.target_id == target_id:
                return True
        else:
            if edge.target_id == source_id and edge.source_id == target_id:
                return True
    return False


def validate_hop_proposal(
    *,
    proposal: HopProposal,
    snapshot: GraphSnapshot,
    filing_accessions: set[str],
    budgets: NavigationBudgetState,
    scope_key: str,
) -> HopValidationResult:
    stage = proposal.stage.value
    ok, reason = budgets.can_visit(stage, scope_key)
    if not ok:
        return HopValidationResult(
            status="rejected",
            rejection_code=reason,
            rationale="navigation budget exhausted",
        )

    if proposal.source_node_id and proposal.source_node_id not in {
        n.node_id for n in snapshot.nodes
    }:
        return HopValidationResult(
            status="rejected",
            rejection_code="invalid_source",
            rationale="source node not in snapshot",
        )

    lim = budgets.limits.max_candidates_per_proposal
    candidates = proposal.candidates[:lim]
    if not candidates:
        return HopValidationResult(
            status="rejected",
            rejection_code="no_valid_candidate",
            rationale="empty candidate list",
        )

    best = None
    best_score = -1.0
    for cand in candidates:
        if cand.edge_type not in STRUCTURAL_EDGE_TYPES:
            continue
        if cand.edge_type in (
            GraphEdgeType.TEMPORAL_TRANSITION,
            GraphEdgeType.SEMANTIC_SIMILARITY,
        ):
            return HopValidationResult(
                status="rejected",
                rejection_code="disallowed_edge",
                rationale=f"edge type {cand.edge_type.value} not allowed for agent hops",
            )
        if not _edge_exists(
            snapshot,
            proposal.source_node_id,
            cand.target_node_id,
            cand.edge_type,
            cand.direction,
        ):
            continue
        acc = accession_from_node_id(cand.target_node_id)
        if acc and acc not in filing_accessions:
            continue
        if cand.score > best_score:
            best = cand
            best_score = cand.score

    if best is None:
        return HopValidationResult(
            status="rejected",
            rejection_code="no_valid_candidate",
            rationale="no candidate passed structural and scope checks",
        )

    visit = NavigationVisit(
        stage=proposal.stage,
        source_node_id=proposal.source_node_id,
        edge_type=best.edge_type,
        target_node_id=best.target_node_id,
        accession=accession_from_node_id(best.target_node_id),
        hop_index=budgets.total_visits,
    )
    return HopValidationResult(
        status="approved",
        approved_hop=visit,
        rationale="approved structural hop",
    )


def is_chunk_node(node_type: GraphNodeType) -> bool:
    return node_type in (
        GraphNodeType.CHUNK_TABLE,
        GraphNodeType.CHUNK_ROW,
        GraphNodeType.CHUNK_PARAGRAPH,
        GraphNodeType.CHUNK_XBRL_FACT,
    )
