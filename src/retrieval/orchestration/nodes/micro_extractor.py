"""Micro routing: graph-native chunk extraction (009)."""

from __future__ import annotations

from retrieval.navigation.walker import run_micro_navigation
from retrieval.orchestration.state import AgentState


def micro_extractor(state: AgentState, *, graph_api) -> dict:
    result = run_micro_navigation(state, graph_api=graph_api)
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
