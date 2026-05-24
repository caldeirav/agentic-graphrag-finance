"""Deterministic trajectory validation rules (010)."""

from __future__ import annotations

import re

from models.enums import QueryStatus
from models.evaluation import TrajectoryValidationResult, ValidationReason, ValidationStatus
from models.trajectory import TRAJECTORY_SCHEMA_VERSION, AgentTrajectorySnapshot

_SUCCESS_STATUSES = {
    QueryStatus.SUCCESS,
}

_SEC_ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")


def validate_trajectory(snapshot: AgentTrajectorySnapshot) -> TrajectoryValidationResult:
    reasons: list[ValidationReason] = []

    if not snapshot.schema_version:
        reasons.append(
            ValidationReason(
                code="MISSING_SCHEMA_VERSION",
                field="schema_version",
                message="schema_version is required",
            )
        )

    if not snapshot.query_id:
        reasons.append(
            ValidationReason(
                code="MISSING_QUERY_ID",
                field="query_id",
                message="query_id is required",
            )
        )

    if snapshot.plan is None or not snapshot.plan.intent_summary:
        reasons.append(
            ValidationReason(
                code="MISSING_PLAN",
                field="plan.intent_summary",
                message="plan.intent_summary is required",
            )
        )

    route_accessions = {r.accession for r in snapshot.document_route if r.accession}

    if (
        snapshot.status in _SUCCESS_STATUSES
        and not snapshot.document_route
        and snapshot.absent_reason not in ("macro_binding_failed", "scope_error")
    ):
        reasons.append(
            ValidationReason(
                code="EMPTY_DOCUMENT_ROUTE",
                field="document_route",
                message="successful ask requires document route",
            )
        )

    if not snapshot.graph_traversal and not snapshot.evidence:
        if snapshot.absent_reason is None and snapshot.status in _SUCCESS_STATUSES:
            reasons.append(
                ValidationReason(
                    code="MISSING_ABSENT_REASON",
                    field="graph_traversal",
                    message="empty traversal/evidence requires absent_reason",
                )
            )

    non_reproducible = False
    for i, hop in enumerate(snapshot.graph_traversal):
        prefix = f"graph_traversal[{i}]"
        if not hop.node_type:
            reasons.append(
                ValidationReason(
                    code="MISSING_NODE_TYPE",
                    field=f"{prefix}.node_type",
                    message="hop missing node_type",
                )
            )
        if not hop.edge_type:
            reasons.append(
                ValidationReason(
                    code="MISSING_EDGE_TYPE",
                    field=f"{prefix}.edge_type",
                    message="hop missing edge_type",
                )
            )
        if not hop.edge_id and not hop.edge_type:
            reasons.append(
                ValidationReason(
                    code="INVALID_HOP_EDGE",
                    field=prefix,
                    message="hop must have edge_type",
                )
            )
        if (
            route_accessions
            and hop.accession_prefix
            and _SEC_ACCESSION.match(hop.accession_prefix)
            and hop.accession_prefix not in route_accessions
        ):
            non_reproducible = True
            reasons.append(
                ValidationReason(
                    code="ORPHAN_HOP_ACCESSION",
                    field=f"{prefix}.accession_prefix",
                    message=f"hop accession {hop.accession_prefix} not in document route",
                )
            )

    for i, ev in enumerate(snapshot.evidence):
        prefix = f"evidence[{i}]"
        if not ev.content_hash:
            reasons.append(
                ValidationReason(
                    code="MISSING_CONTENT_HASH",
                    field=f"{prefix}.content_hash",
                    message="evidence missing content_hash",
                )
            )
        if not ev.citation_label:
            reasons.append(
                ValidationReason(
                    code="MISSING_CITATION_LABEL",
                    field=f"{prefix}.citation_label",
                    message="evidence missing citation_label",
                )
            )
        if (
            route_accessions
            and ev.accession
            and _SEC_ACCESSION.match(ev.accession)
            and ev.accession not in route_accessions
        ):
            non_reproducible = True
            reasons.append(
                ValidationReason(
                    code="EVIDENCE_ACCESSION_MISMATCH",
                    field=f"{prefix}.accession",
                    message=f"evidence accession {ev.accession} not in document route",
                )
            )

    if non_reproducible:
        status = ValidationStatus.NON_REPRODUCIBLE
    elif reasons:
        status = ValidationStatus.INCOMPLETE
    else:
        status = ValidationStatus.COMPLETE

    return TrajectoryValidationResult(
        status=status,
        reason_codes=reasons,
        snapshot_schema_version=snapshot.schema_version or TRAJECTORY_SCHEMA_VERSION,
    )
