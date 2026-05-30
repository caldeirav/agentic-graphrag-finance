"""Compile LangGraph StateGraph."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from models.reproduction import VariantCapabilities
from retrieval.orchestration.nodes.intent_router import intent_router
from retrieval.orchestration.nodes.macro_router import macro_router
from retrieval.orchestration.nodes.meso_router import meso_router
from retrieval.orchestration.nodes.micro_extractor import micro_extractor
from retrieval.orchestration.state import AgentState
from retrieval.orchestration.trace_payloads import build_stage_trace_payload
from retrieval.synthesis import synthesize
from tracing.console_trace.context import get_trace_reporter
from tracing.console_trace.emitter import StageTimer, trace_stage_start


def get_ask_graph_stage_ids(
    variant_profile: VariantCapabilities | None = None,
) -> set[str]:
    """Stage node names (excludes LangGraph __start__/__end__)."""
    profile = variant_profile or VariantCapabilities()
    stages = {"macro_router", "intent_router", "meso_router", "micro_extractor", "synthesize"}
    if profile.disable_macro_router:
        stages.discard("macro_router")
    if profile.disable_graph_walker:
        stages -= {"meso_router", "micro_extractor"}
    return stages


def _merge_trace_into_result(result: dict, extra: dict) -> dict:
    if not extra.get("trace_events"):
        return result
    merged = dict(result)
    events = list(merged.get("trace_events") or [])
    events.extend(extra.get("trace_events") or [])
    merged["trace_events"] = events
    return merged


def _traced_node(
    fn: Callable[..., dict],
    stage_id: str,
    *,
    graph_api: Any = None,
) -> Callable[[AgentState], dict]:
    def _run(state: AgentState) -> dict:
        reporter = get_trace_reporter()
        timer = StageTimer(stage_id)
        start_patch = trace_stage_start(stage_id)
        accumulated: dict = {"trace_events": list(start_patch.get("trace_events") or [])}

        if graph_api is not None:
            result = fn(state, graph_api=graph_api)
        else:
            result = fn(state)

        built = build_stage_trace_payload(stage_id, {**state, **result})
        from tracing.console_trace.emitter import trace_stage_end

        end_patch = trace_stage_end(
            stage_id,
            duration_ms=timer.elapsed_ms,
            decision_summary=built["decision_summary"],
            payload=built.get("payload"),
        )
        accumulated["trace_events"].extend(end_patch.get("trace_events") or [])

        merged = _merge_trace_into_result(result, accumulated)
        if reporter is not None:
            reporter.flush_stage(stage_id, {**state, **merged})
        return merged

    def wrapped(state: AgentState) -> dict:
        try:
            import mlflow

            traced = mlflow.trace(name=f"stage.{stage_id}")(_run)
            return traced(state)
        except Exception:
            return _run(state)

    return wrapped


def build_agent_graph(
    graph_api,
    *,
    variant_profile: VariantCapabilities | None = None,
):
    profile = variant_profile or VariantCapabilities()
    skip_macro = profile.disable_macro_router
    skip_walker = profile.disable_graph_walker

    g = StateGraph(AgentState)

    if not skip_macro:
        g.add_node(
            "macro_router",
            _traced_node(macro_router, "macro_router", graph_api=graph_api),
        )
    g.add_node("intent_router", _traced_node(intent_router, "intent_router"))

    if not skip_walker:
        g.add_node(
            "meso_router",
            _traced_node(meso_router, "meso_router", graph_api=graph_api),
        )
        g.add_node(
            "micro_extractor",
            _traced_node(micro_extractor, "micro_extractor", graph_api=graph_api),
        )

    g.add_node("synthesize", _traced_node(synthesize, "synthesize"))

    def _route_after_macro(state: AgentState) -> str:
        if state.get("macro_binding_failed"):
            return "scope_error"
        return "continue"

    if skip_macro:
        g.set_entry_point("intent_router")
    else:
        g.set_entry_point("macro_router")
        g.add_conditional_edges(
            "macro_router",
            _route_after_macro,
            {"scope_error": "synthesize", "continue": "intent_router"},
        )

    if skip_walker:
        g.add_edge("intent_router", "synthesize")
    else:
        g.add_edge("intent_router", "meso_router")
        g.add_edge("meso_router", "micro_extractor")
        g.add_edge("micro_extractor", "synthesize")

    g.add_edge("synthesize", END)

    return g.compile()
