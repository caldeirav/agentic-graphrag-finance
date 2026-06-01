"""Meso routing: graph-native section navigation (009)."""

from __future__ import annotations

import json

from models.query import SectionCandidate
from retrieval.navigation.walker import run_meso_navigation
from retrieval.orchestration.state import AgentState


def meso_router(state: AgentState, *, graph_api) -> dict:
    if state.get("variant_disable_graph_walker"):
        paths = json.loads(state.get("expected_section_paths_json") or "[]")
        candidates = [
            SectionCandidate(
                section_node_id=path,
                score=1.0,
                accession=path.split("/")[0] if "/" in path else "",
            )
            for path in paths
        ]
        return {"section_candidates": candidates, "meso_section_trace": []}
    return run_meso_navigation(state, graph_api=graph_api)


def rank_sections_heuristic(state: AgentState, *, graph_api) -> dict:
    from retrieval.navigation.walker import rank_sections_heuristic as _disabled

    return _disabled(state, graph_api=graph_api)
