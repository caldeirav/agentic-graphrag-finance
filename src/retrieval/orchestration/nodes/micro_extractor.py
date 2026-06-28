"""Micro routing: graph-native chunk extraction (009)."""

from __future__ import annotations

from retrieval.navigation.walker import run_micro_navigation
from retrieval.orchestration.state import AgentState
from retrieval.skills.metric_intent import heuristic_metric_intent
from retrieval.skills.numeric_evidence_enrichment import (
    enrich_numeric_evidence,
    enrichment_trace_json,
)


def micro_extractor(state: AgentState, *, graph_api) -> dict:
    result = run_micro_navigation(state, graph_api=graph_api)
    query = str(state.get("query") or "")
    filing_set = list(state.get("filing_set") or [])
    snapshot_id = str(state.get("snapshot_id") or "")
    if query and filing_set and snapshot_id:
        enriched = enrich_numeric_evidence(
            list(result.get("evidence_chunks") or []),
            query,
            filing_set,
            snapshot_id=snapshot_id,
            graph_api=graph_api,
            metric_intent=heuristic_metric_intent(query),
        )
        result = dict(result)
        result["evidence_chunks"] = enriched.evidence
        if enriched.added_chunk_ids:
            result["evidence_enrichment_json"] = enrichment_trace_json(enriched)
    if not state.get("variant_xbrl_only"):
        return result
    chunks = list(result.get("evidence_chunks") or [])
    filtered = [
        c
        for c in chunks
        if getattr(c, "source_type", None) and str(getattr(c.source_type, "value", c.source_type)) != "HTML"
    ]
    out = dict(result)
    out["evidence_chunks"] = filtered
    return out
