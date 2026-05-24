"""Build structured trace payloads from agent state (no display logic)."""

from __future__ import annotations

from retrieval.context_budget import load_context_budget
from retrieval.orchestration.state import AgentState


def build_macro_router_trace_payload(state: AgentState) -> dict:
    filing_set = list(state.get("filing_set") or [])
    plan = state.get("macro_plan")
    record = state.get("macro_binding_record")
    accessions = [f.accession for f in filing_set]
    comparison = ""
    if plan and plan.temporal_scope:
        comparison = str(plan.temporal_scope.comparison_mode)
    binding_source = ""
    validation_status = ""
    failure_codes: list[str] = []
    proposal_summary = ""
    rationale = ""
    if record is not None:
        traj = record.to_trajectory_dict()
        binding_source = traj.get("binding_source", "")
        validation_status = traj.get("validation_status", "")
        failure_codes = list(traj.get("failure_codes") or [])
        rationale = traj.get("rationale", "")
        if record.proposal:
            proposal_summary = (record.proposal.intent_summary or "")[:120]
    elif plan:
        binding_source = plan.binding_source or ""
        rationale = plan.rationale or ""

    summary = plan.intent_summary[:120] if plan else "macro routing"
    if binding_source == "cli_prebound" and filing_set:
        summary = f"pre-bound {len(filing_set)} filing(s)"
    if validation_status == "failed":
        summary = f"macro binding failed: {failure_codes[0] if failure_codes else 'unknown'}"

    return {
        "decision_summary": summary,
        "payload": {
            "pre_bound": binding_source == "cli_prebound",
            "llm_skipped": bool(state.get("macro_llm_skipped")),
            "binding_source": binding_source,
            "validation_status": validation_status,
            "selected_accessions": accessions,
            "filing_accessions": accessions,
            "comparison_mode": comparison,
            "failure_codes": failure_codes,
            "proposal_summary": proposal_summary,
            "rationale": rationale[:300] if rationale else "",
        },
    }


def build_intent_router_trace_payload(state: AgentState) -> dict:
    trace = state.get("intent_trace")
    if trace is None:
        return {"decision_summary": "intent not classified", "payload": {}}
    payload = {
        "query_intent": trace.query_intent.value,
        "intent_source": trace.intent_source.value,
        "source_bias_applied": trace.source_bias_applied.value,
        "router_fallback_reason": (
            trace.router_fallback_reason.value if trace.router_fallback_reason else None
        ),
        "router_model_id": trace.router_model_id,
        "router_latency_ms": trace.router_latency_ms,
    }
    summary = (
        f"intent={trace.query_intent.value} source={trace.intent_source.value} "
        f"bias={trace.source_bias_applied.value}"
    )
    if trace.router_fallback_reason:
        summary += f" fallback={trace.router_fallback_reason.value}"
    return {"decision_summary": summary, "payload": payload}


def _navigation_payload(state: AgentState) -> dict:
    nt = state.get("navigation_trace")
    if nt is None:
        return {}
    if hasattr(nt, "to_trajectory_dict"):
        return nt.to_trajectory_dict()
    return nt if isinstance(nt, dict) else {}


def build_meso_router_trace_payload(state: AgentState) -> dict:
    candidates = list(state.get("section_candidates") or [])
    section_trace = list(state.get("meso_section_trace") or [])
    nav = _navigation_payload(state)
    cfg = load_trace_config_limits()
    limit = cfg["top_sections"]
    if not section_trace and candidates:
        top = [
            {
                "section_node_id": c.section_node_id,
                "score": round(c.score, 3),
                "path": c.path[:3],
            }
            for c in candidates[:limit]
        ]
    else:
        top = section_trace[:limit]
    edge_types = nav.get("structural_edge_types_used") or []
    sample_path = ""
    ranks = nav.get("meso_ranks") or []
    if ranks:
        path = ranks[0].get("path", {}) if isinstance(ranks[0], dict) else {}
        seq = path.get("edge_type_sequence") or []
        sample_path = " → ".join(seq[:6])
    toc_plans = nav.get("toc_plans") or []
    discovery = nav.get("section_discovery_mode", "graph_native")
    summary = f"graph-native: {len(candidates)} section candidate(s)"
    if discovery == "toc_planner" and toc_plans:
        primary = toc_plans[0].get("primary_narrative_kind", "")
        summary = f"toc_planner ({primary}): {len(candidates)} section(s)"
    return {
        "decision_summary": summary,
        "payload": {
            "navigation_mode": "graph_native",
            "section_discovery_mode": discovery,
            "toc_plans": toc_plans[:2],
            "candidate_count": len(candidates),
            "top_section_ids": [r.get("section_node_id", r.get("section_id", "")) for r in top],
            "top_sections": top,
            "edge_types_used": edge_types,
            "visit_count": nav.get("visit_counts", {}),
            "sample_path": sample_path,
            "rejected_count": len(nav.get("rejected_proposals") or []),
            "budget_exhausted": bool(nav.get("budget_exhausted")),
        },
    }


def build_micro_extractor_trace_payload(state: AgentState) -> dict:
    chunks = list(state.get("evidence_chunks") or [])
    intent_trace = state.get("intent_trace")
    bias = intent_trace.source_bias_applied.value if intent_trace else "blended"
    cfg = load_trace_config_limits()
    rank_trace = list(state.get("micro_rank_trace") or [])
    if rank_trace:
        ranked_preview = rank_trace[: cfg["top_evidence"]]
    else:
        ranked_preview = [
            {
                "chunk_node_id": c.chunk_node_id,
                "source_type": getattr(c.source_type, "value", str(c.source_type)),
                "section_id": c.section_id,
                "excerpt_preview": c.excerpt[: cfg["excerpt"]] + (
                    "..." if len(c.excerpt) > cfg["excerpt"] else ""
                ),
            }
            for c in chunks[: cfg["top_evidence"]]
        ]
    ranked = state.get("micro_ranked_count")
    count_after = len(chunks)
    count_before = ranked if ranked is not None else count_after
    nav = _navigation_payload(state)
    edge_types = nav.get("structural_edge_types_used") or []
    micro_paths = nav.get("micro_paths") or []
    sample_path = ""
    if micro_paths:
        seq = micro_paths[0].get("edge_type_sequence") or []
        sample_path = " → ".join(seq[:8])
    return {
        "decision_summary": (
            f"graph-native evidence {count_before}→{count_after} bias={bias} "
            f"top={min(len(ranked_preview), cfg['top_evidence'])}"
        ),
        "payload": {
            "navigation_mode": "graph_native",
            "count_before": count_before,
            "count_after": count_after,
            "source_bias": bias,
            "ranked": ranked_preview,
            "edge_types_used": edge_types,
            "visit_count": nav.get("visit_counts", {}),
            "sample_path": sample_path,
            "rejected_count": len(nav.get("rejected_proposals") or []),
        },
    }


def build_synthesize_trace_payload(state: AgentState) -> dict:
    chunks = list(state.get("evidence_chunks") or [])
    answer = state.get("answer")
    status = state.get("status")
    budget = load_context_budget()
    retry = bool(state.get("synthesis_retry_budget"))
    return {
        "decision_summary": (
            f"synthesis evidence={len(chunks)} status={status} "
            f"ctx={budget.get('context_tokens', '?')}"
            + (" retry=tighter" if retry else "")
        ),
        "payload": {
            "evidence_in_prompt": min(len(chunks), budget.get("max_evidence_chunks", 5)),
            "context_tokens": budget.get("context_tokens"),
            "max_evidence_chunks": budget.get("max_evidence_chunks"),
            "max_excerpt_chars": budget.get("max_excerpt_chars"),
            "sufficiency": getattr(answer, "sufficiency", None) if answer else None,
            "retry_tighter_budget": retry,
        },
    }


def load_trace_config_limits() -> dict:
    from tracing.console_trace.config import load_trace_config

    cfg = load_trace_config()
    return {
        "excerpt": int(cfg.get("excerpt_preview_chars", 400)),
        "top_evidence": int(cfg.get("top_evidence_preview", 10)),
        "top_sections": int(cfg.get("top_section_candidates", 10)),
        "top_structural_paths": int(cfg.get("top_structural_paths", 3)),
    }


def structural_paths_for_evidence(
    state: AgentState,
    *,
    limit: int = 3,
) -> list[dict]:
    """Top evidence chunks with structural path edge types from graph_traversal."""
    evidence = list(state.get("evidence_chunks") or [])[:limit]
    visits = {
        v.get("node_id"): v
        for v in state.get("graph_traversal") or []
        if isinstance(v, dict) and v.get("node_id")
    }
    out: list[dict] = []
    for chunk in evidence:
        visit = visits.get(chunk.chunk_node_id, {})
        edges = list(visit.get("path_edge_types") or [])
        nodes = list(visit.get("path_node_ids") or [])
        row: dict = {
            "chunk_node_id": chunk.chunk_node_id,
            "path_edge_types": edges,
        }
        if nodes:
            row["path_node_ids"] = nodes[-6:]
        out.append(row)
    return out


_PAYLOAD_BUILDERS = {
    "macro_router": build_macro_router_trace_payload,
    "intent_router": build_intent_router_trace_payload,
    "meso_router": build_meso_router_trace_payload,
    "micro_extractor": build_micro_extractor_trace_payload,
    "synthesize": build_synthesize_trace_payload,
}


def build_stage_trace_payload(stage_id: str, state: AgentState) -> dict:
    builder = _PAYLOAD_BUILDERS.get(stage_id)
    if builder is None:
        return {"decision_summary": stage_id, "payload": {}}
    return builder(state)
