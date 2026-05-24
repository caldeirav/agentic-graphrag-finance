"""Meso routing: graph-native section navigation (009)."""

from __future__ import annotations

from retrieval.navigation.walker import run_meso_navigation
from retrieval.orchestration.state import AgentState


def meso_router(state: AgentState, *, graph_api) -> dict:
    return run_meso_navigation(state, graph_api=graph_api)


def rank_sections_heuristic(state: AgentState, *, graph_api) -> dict:
    from retrieval.navigation.walker import rank_sections_heuristic as _disabled

    return _disabled(state, graph_api=graph_api)
