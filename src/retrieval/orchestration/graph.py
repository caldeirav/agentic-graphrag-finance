"""Compile LangGraph StateGraph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from retrieval.orchestration.nodes.macro_router import macro_router
from retrieval.orchestration.nodes.meso_router import meso_router
from retrieval.orchestration.nodes.micro_extractor import micro_extractor
from retrieval.orchestration.state import AgentState
from retrieval.synthesis import synthesize


def build_agent_graph(graph_api):
    g = StateGraph(AgentState)

    g.add_node("macro_router", lambda s: macro_router(s, graph_api=graph_api))
    g.add_node("meso_router", lambda s: meso_router(s, graph_api=graph_api))
    g.add_node("micro_extractor", lambda s: micro_extractor(s, graph_api=graph_api))
    g.add_node("synthesize", synthesize)

    g.set_entry_point("macro_router")
    g.add_edge("macro_router", "meso_router")
    g.add_edge("meso_router", "micro_extractor")
    g.add_edge("micro_extractor", "synthesize")
    g.add_edge("synthesize", END)

    return g.compile()
