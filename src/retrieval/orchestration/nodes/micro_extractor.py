"""Micro routing: graph-native chunk extraction (009)."""

from __future__ import annotations

from retrieval.navigation.walker import run_micro_navigation
from retrieval.orchestration.state import AgentState


def micro_extractor(state: AgentState, *, graph_api) -> dict:
    return run_micro_navigation(state, graph_api=graph_api)
