"""Build versioned agent trajectory snapshots from LangGraph state."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from models.enums import EvidenceSourceType

from graph.accession import accession_from_node_id
from models.enums import QueryStatus
from models.filing import FilingRef
from models.query import EvidenceChunk, IntentRouterTrace, MacroPlan
from models.trajectory import (
    TRAJECTORY_SCHEMA_VERSION,
    AgentTrajectorySnapshot,
    EvidenceEntry,
    FilingRouteEntry,
    GraphHop,
    StageDecision,
    SynthesisPath,
    TrajectoryPlan,
)

_AUDIT_HOP_NODE_IDS = frozenset({"macro", "intent_router", "intent", "meso", "micro", "synthesize"})


def _resolve_accession_prefix(node_id: str, filing_accessions: set[str]) -> str:
    """Map graph node id to SEC accession; empty for audit-only hops."""
    if node_id in _AUDIT_HOP_NODE_IDS:
        return ""
    acc = accession_from_node_id(node_id)
    if acc and acc in filing_accessions:
        return acc
    if acc:
        return acc
    if "::" in node_id:
        prefix = node_id.split("::", 1)[0]
        if prefix in filing_accessions:
            return prefix
    if node_id.startswith("000"):
        parts = node_id.split("-")
        if len(parts) >= 3:
            candidate = "-".join(parts[:3])
            if candidate in filing_accessions:
                return candidate
    return ""


def _infer_node_type(node_id: str, stage: str) -> str:
    lowered = node_id.lower()
    if "section" in lowered or "mda" in lowered or "item" in lowered:
        return "section"
    if "table" in lowered or "xbrl" in lowered:
        return "table"
    if "chunk" in lowered or "paragraph" in lowered:
        return "chunk"
    if stage == "macro":
        return "filing"
    return "node"


def _build_plan(state: dict[str, Any]) -> TrajectoryPlan:
    macro_plan: MacroPlan | None = state.get("macro_plan")
    intent_trace: IntentRouterTrace | None = state.get("intent_trace")
    binding = state.get("macro_binding_record")
    rationale = ""
    steps: list[StageDecision] = []
    intent_summary = state.get("query", "")[:200]

    if macro_plan is not None:
        intent_summary = macro_plan.intent_summary or intent_summary
        rationale = macro_plan.rationale or rationale
        if macro_plan.binding_source:
            steps.append(
                StageDecision(
                    stage="macro",
                    description=f"binding_source={macro_plan.binding_source}",
                    selected=True,
                )
            )

    if binding is not None and hasattr(binding, "to_trajectory_dict"):
        bd = binding.to_trajectory_dict()
        rationale = bd.get("rationale") or rationale
        for acc in bd.get("selected_accessions") or []:
            steps.append(
                StageDecision(stage="macro", description=f"selected accession {acc}", selected=True)
            )

    if intent_trace is not None:
        steps.append(
            StageDecision(
                stage="intent",
                description=f"intent={intent_trace.query_intent.value} source={intent_trace.intent_source.value}",
                selected=True,
            )
        )

    if not rationale:
        rationale = "Agent graph execution path"

    return TrajectoryPlan(
        intent_summary=intent_summary,
        steps_considered=steps,
        chosen_path_rationale=rationale,
        rejected_alternatives=[],
    )


def _build_document_route(filing_set: list[FilingRef]) -> list[FilingRouteEntry]:
    routes: list[FilingRouteEntry] = []
    for f in filing_set:
        label = None
        if f.period_end:
            label = f"FY{f.period_end.year}" if f.form_type == "10-K" else str(f.period_end)
        routes.append(
            FilingRouteEntry(
                accession=f.accession,
                form_type=f.form_type,
                cik=f.cik,
                filed_at=str(f.filed_at) if f.filed_at else None,
                period_end=str(f.period_end) if f.period_end else None,
                fiscal_period_label=label,
            )
        )
    return routes


def _build_graph_hops(state: dict[str, Any], filing_accessions: set[str]) -> list[GraphHop]:
    hops: list[GraphHop] = []
    hop_index = 0
    for v in state.get("graph_traversal") or []:
        if not isinstance(v, dict):
            continue
        node_id = str(v.get("node_id") or "")
        stage = str(v.get("stage") or "meso")
        if node_id in _AUDIT_HOP_NODE_IDS and not node_id.startswith("doc-"):
            continue
        edge_types = list(v.get("path_edge_types") or [])
        edge_type = str(v.get("edge_type") or (edge_types[0] if edge_types else "CONTAINS"))
        prefix = _resolve_accession_prefix(node_id, filing_accessions)
        hops.append(
            GraphHop(
                hop_index=hop_index,
                stage=stage,
                node_id=node_id,
                node_type=_infer_node_type(node_id, stage),
                edge_type=edge_type,
                edge_id=v.get("edge_id"),
                accession_prefix=prefix or (next(iter(filing_accessions), "") if filing_accessions else ""),
            )
        )
        hop_index += 1
    return hops


def _build_evidence(state: dict[str, Any], filing_accessions: set[str]) -> list[EvidenceEntry]:
    prompt_ids = set(state.get("synthesis_prompt_chunk_ids") or [])
    entries: list[EvidenceEntry] = []
    for chunk in state.get("evidence_chunks") or []:
        if not isinstance(chunk, EvidenceChunk):
            continue
        st = chunk.source_type.value if hasattr(chunk.source_type, "value") else str(chunk.source_type)
        acc = chunk.accession or _resolve_accession_prefix(chunk.chunk_node_id, filing_accessions)
        entries.append(
            EvidenceEntry(
                chunk_node_id=chunk.chunk_node_id,
                content_hash=chunk.content_hash or "",
                citation_label=chunk.citation_label or chunk.chunk_node_id,
                source_type=st.lower() if st else "narrative",
                accession=acc,
                section_id=chunk.section_id or None,
                in_prompt=chunk.chunk_node_id in prompt_ids if prompt_ids else True,
            )
        )
    return entries


def _resolve_synthesis_path(state: dict[str, Any]) -> SynthesisPath:
    raw = state.get("synthesis_path")
    if raw:
        try:
            return SynthesisPath(str(raw))
        except ValueError:
            pass
    if state.get("synthesis_yoy_fallback") or state.get("synthesis_fallback") == "yoy_deterministic":
        return SynthesisPath.DETERMINISTIC_FALLBACK
    import os

    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        return SynthesisPath.TEMPLATE
    return SynthesisPath.LIVE_LLM


def _parse_iso_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _evidence_dict_to_chunk(entry: dict[str, Any]) -> EvidenceChunk:
    raw_type = str(entry.get("source_type") or "narrative").upper()
    try:
        source_type = EvidenceSourceType(raw_type)
    except ValueError:
        source_type = EvidenceSourceType.HTML
    return EvidenceChunk(
        chunk_node_id=str(entry.get("chunk_node_id") or ""),
        excerpt="",
        content_hash=str(entry.get("content_hash") or ""),
        citation_label=str(entry.get("citation_label") or entry.get("chunk_node_id") or ""),
        source_type=source_type,
        accession=str(entry.get("accession") or ""),
        section_id=str(entry.get("section_id") or ""),
    )


def normalize_trajectory_state(state: dict[str, Any]) -> dict[str, Any]:
    """Hydrate LangGraph fields from a serialized AgentTrajectorySnapshot dict."""
    normalized = dict(state)
    if not normalized.get("evidence_chunks") and normalized.get("evidence"):
        chunks: list[EvidenceChunk] = []
        for entry in normalized["evidence"]:
            if isinstance(entry, EvidenceChunk):
                chunks.append(entry)
            elif isinstance(entry, dict):
                chunks.append(_evidence_dict_to_chunk(entry))
            elif hasattr(entry, "model_dump"):
                chunks.append(_evidence_dict_to_chunk(entry.model_dump()))
        normalized["evidence_chunks"] = chunks

    if not normalized.get("filing_set") and normalized.get("document_route"):
        filing_set: list[FilingRef] = []
        for route in normalized["document_route"]:
            if isinstance(route, FilingRef):
                filing_set.append(route)
                continue
            if not isinstance(route, dict):
                continue
            filed_at = _parse_iso_date(route.get("filed_at") or "1970-01-01")
            period_end = _parse_iso_date(route.get("period_end") or filed_at)
            filing_set.append(
                FilingRef(
                    cik=str(route.get("cik") or ""),
                    accession=str(route.get("accession") or ""),
                    form_type=str(route.get("form_type") or "10-K"),
                    filed_at=filed_at,
                    period_end=period_end,
                    source_uri="",
                )
            )
        normalized["filing_set"] = filing_set

    if normalized.get("query_text") and not normalized.get("query"):
        normalized["query"] = normalized["query_text"]
    return normalized


def _resolve_absent_reason(state: dict[str, Any]) -> str | None:
    if state.get("macro_binding_failed"):
        return "macro_binding_failed"
    status = state.get("status", QueryStatus.SUCCESS)
    if status == QueryStatus.INSUFFICIENT_EVIDENCE:
        return "insufficient_evidence"
    if status == QueryStatus.ERROR:
        return "scope_error"
    if not state.get("graph_traversal") and not state.get("evidence_chunks"):
        return state.get("absent_reason")
    return None


def build_agent_trajectory_snapshot(
    state: dict[str, Any],
    *,
    trace_id: str | None = None,
    mlflow_run_id: str = "",
    issuer_id: str = "",
) -> AgentTrajectorySnapshot:
    state = normalize_trajectory_state(state)
    query_id = str(state.get("query_id") or uuid.uuid4())
    filing_set: list[FilingRef] = list(state.get("filing_set") or [])
    filing_accessions = {f.accession for f in filing_set if f.accession}

    macro_binding = None
    record = state.get("macro_binding_record")
    if record is not None and hasattr(record, "to_trajectory_dict"):
        macro_binding = record.to_trajectory_dict()

    nav_trace = None
    nt = state.get("navigation_trace")
    if nt is not None:
        nav_trace = nt.to_trajectory_dict() if hasattr(nt, "to_trajectory_dict") else nt

    intent_router = state.get("intent_trace")
    if intent_router is not None and not isinstance(intent_router, IntentRouterTrace):
        intent_router = None

    mlflow_trace_id = trace_id
    if mlflow_trace_id is None:
        try:
            import mlflow

            mlflow_trace_id = mlflow.get_last_active_trace_id()
        except Exception:
            mlflow_trace_id = None

    return AgentTrajectorySnapshot(
        schema_version=TRAJECTORY_SCHEMA_VERSION,
        query_id=query_id,
        query_text=str(state.get("query") or ""),
        issuer_id=issuer_id or str(state.get("issuer_id") or ""),
        snapshot_id=str(state.get("snapshot_id") or ""),
        evaluation_as_of=str(state.get("evaluation_as_of") or date.today().isoformat()),
        mlflow_run_id=mlflow_run_id,
        mlflow_trace_id=mlflow_trace_id,
        status=state.get("status", QueryStatus.SUCCESS),
        synthesis_path=_resolve_synthesis_path(state),
        absent_reason=_resolve_absent_reason(state),
        plan=_build_plan(state),
        document_route=_build_document_route(filing_set),
        graph_traversal=_build_graph_hops(state, filing_accessions),
        evidence=_build_evidence(state, filing_accessions),
        macro_binding=macro_binding,
        navigation_trace=nav_trace,
        intent_router=intent_router,
    )
